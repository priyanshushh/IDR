from passlib.context import CryptContext
from app.core.config import settings
from datetime import datetime,timedelta
import jwt
from fastapi.security import OAuth2PasswordBearer
from app.models import User
from app.database.dependencies import get_db
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Depends
from fastapi import HTTPException
from app.schemas.user import UserProfileSchema
from app.models.company import CompanyMember

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/signin")

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password:str):
    return pwd_context.hash(password)

def verify_password(password:str,hashed_password:str):
    return pwd_context.verify(password,hashed_password)

def create_access_token(claims:dict)->str:
    to_encode = claims.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode["exp"] = expire
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

    return encoded_jwt

def decode_access_token(token:str):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def create_refresh_token(claims:dict)->str:
    to_encode = claims.copy()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode["exp"] = expire
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt
    
    
def decode_refresh_token(token:str):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str, Depends(oauth2_scheme)],
)->UserProfileSchema:
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )

    user_id = payload.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )

    schema_name = payload.get("schema_name")

    if not schema_name:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )

    result = await db.execute(
        select(User).where(User.id == user_id)
    )


    user = result.scalars().first()
    member_result = await db.execute(
        select(CompanyMember).where(CompanyMember.user_id == user_id)
    )
    member = member_result.scalars().first()


    final_user = UserProfileSchema(
        id=user.id,
        name=user.name,
        must_change_password=user.must_change_password,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        company_id=member.company_id,
        role=member.role,
        status=member.status,
        schema_name=schema_name,
    )
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
        )

    return final_user


CurrentUser = Annotated[User, Depends(get_current_user)]