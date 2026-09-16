import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email_domains import extract_domain, is_banned_email_domain
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password, decode_refresh_token
from app.database.tenant_provisioning import provision_tenant_schema
from app.models.company import Company, CompanyMember, RefreshToken
from app.models.user import User
from app.schemas.company import CompanyLoginSchema, CompanySignupSchema


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _issue_refresh_token(self, user_id,schema_name:str) -> tuple[str, RefreshToken]:
        raw_token = create_refresh_token({
            "user_id": str(user_id),
            "jti": secrets.token_urlsafe(16),
            "schema_name": schema_name,
        })
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        row = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days),
            revoked=False,
        )
        return raw_token, row

    async def signup_company(self, payload: CompanySignupSchema):
        domain = extract_domain(payload.email)
        if is_banned_email_domain(domain):
            raise HTTPException(status_code=400, detail="Please sign up with a work email")

        existing = await self.db.execute(select(Company).where(Company.domain == domain))
        if existing.scalars().first():
            raise HTTPException(status_code=409, detail="Your organization already has an account")

        try:
            user = User(
                name=payload.owner_name,
                email=payload.email,
                hashed_password=hash_password(payload.password),
                must_change_password=False,
            )
            self.db.add(user)
            await self.db.flush()

            # id is generated client-side (not left to the DB default) so
            # schema_name can be computed and set *before* this row is ever
            # inserted — schema_name is NOT NULL at the DB level, so the insert
            # itself would fail if we tried to flush first and backfill it after
            # (as an earlier version of this code did).
            company_id = uuid.uuid4()
            schema_name = f"tenant_{company_id.hex}"

            company = Company(
                id=company_id,
                name=payload.company_name,
                domain=domain,
                slug=payload.company_name.replace(" ", "-").lower(),
                plan=payload.plan,
                schema_name=schema_name,
                is_active=True,
            )
            self.db.add(company)
            await self.db.flush()

            # Provisioning (CREATE SCHEMA + the four tenant tables) runs on this
            # same session/transaction, so it commits or rolls back atomically
            # with the company/user/member rows below — see
            # app/database/tenant_provisioning.py.

            self.db.add(CompanyMember(
                user_id=user.id,
                company_id=company.id,
                role="owner",
                status="active",
                invited_by=None,
            ))

            raw_refresh_token, refresh_token_row = self._issue_refresh_token(user.id,schema_name)
            self.db.add(refresh_token_row)

            await self.db.flush()
            await provision_tenant_schema(self.db, schema_name)

            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=409, detail="Your organization already has an account")
        except Exception:
            await self.db.rollback()
            raise

        access_token = create_access_token({
            "user_id": str(user.id),
            "company_id": str(company.id),
            "role": "owner",
            "schema_name": schema_name,
        })

        return {
            "access_token": access_token,
            "refresh_token": raw_refresh_token,
            "token_type": "bearer",
            "must_change_password": user.must_change_password,
            "company_id": str(company.id),
            "role": "owner",
        }
    async def signin(self, email: str, password: str):
        result = await self.db.execute(
            select(User).where(User.email == email)
        )

        user = result.scalars().first()

        if not user or not verify_password(
            password,
            user.hashed_password
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="This account has been deactivated",
            )

        result = await self.db.execute(
            select(CompanyMember, Company.schema_name).join(
                Company, Company.id == CompanyMember.company_id
            ).where(
                CompanyMember.user_id == user.id
            )
        )
        row = result.first()
        company_member, schema_name = row if row else (None, None)

        if not company_member or company_member.status != "active":
            raise HTTPException(
                status_code=403,
                detail="No active company membership",
            )

        try:
            raw_refresh_token, refresh_token_row = self._issue_refresh_token(
                user.id,
                schema_name,
            )

            self.db.add(refresh_token_row)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        access_token = create_access_token({
            "user_id": str(user.id),
            "company_id": str(company_member.company_id),
            "role": company_member.role,
            "schema_name": schema_name,
        })

        return {
            "access_token": access_token,
            "refresh_token": raw_refresh_token,
            "token_type": "bearer",
            "must_change_password": user.must_change_password,
            "company_id": str(company_member.company_id),
            "role": company_member.role,
        }


    async def refresh(self, raw_refresh_token: str):
      
        try:
            payload = decode_refresh_token(raw_refresh_token)
        except Exception:
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token",
            )

        user_id = payload.get("user_id")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token",
            )

        
        token_hash = hashlib.sha256(
            raw_refresh_token.encode()
        ).hexdigest()

    
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash
            )
        )

        refresh_token = result.scalars().first()

        if not refresh_token:
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token",
            )

        
        if refresh_token.revoked:
            raise HTTPException(
                status_code=401,
                detail="Refresh token has been revoked",
            )

    
        if refresh_token.expires_at <= datetime.utcnow():
            raise HTTPException(
                status_code=401,
                detail="Refresh token has expired",
            )

        
        if str(refresh_token.user_id) != str(user_id):
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token",
            )

    
        result = await self.db.execute(
            select(CompanyMember, Company.schema_name).join(
                Company, Company.id == CompanyMember.company_id
            ).where(
                CompanyMember.user_id == refresh_token.user_id,
                CompanyMember.status == "active",
            )
        )

        row = result.first()
        company_member, schema_name = row if row else (None, None)

        if not company_member:
            raise HTTPException(
                status_code=403,
                detail="No active company membership",
            )


        # Rotate refresh token

        refresh_token.revoked = True

        new_raw_refresh_token, new_refresh_token_row = (
            self._issue_refresh_token(refresh_token.user_id)
        )

        self.db.add(new_refresh_token_row)

        # Create new access token
        new_access_token = create_access_token({
            "user_id": str(refresh_token.user_id),
            "company_id": str(company_member.company_id),
            "role": company_member.role,
            "schema_name": schema_name,
        })

        await self.db.commit()

        return {
            "access_token": new_access_token,
            "refresh_token": new_raw_refresh_token,
            "token_type": "bearer",
            "company_id": str(company_member.company_id),
            "role": company_member.role,
        }

    async def logout(self, user: User, raw_refresh_token: str):
        token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()

        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        refresh_token = result.scalars().first()

        # Checking user_id here (not just "does this hash exist") stops one user from
        # revoking a session that isn't theirs, even if they somehow got hold of
        # someone else's raw refresh token string.
        if not refresh_token or str(refresh_token.user_id) != str(user.id):
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        refresh_token.revoked = True
        await self.db.commit()

        return {"detail": "Logged out successfully"}
        