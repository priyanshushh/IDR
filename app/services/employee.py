from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.company import Company
# from app.models.employee import Employee
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy import update
from app.models.company import CompanyMember
from app.schemas.employee import InviteEmployeeSchema
from app.utils.generate_random_password import generate_random_password
from app.core.security import hash_password
from sqlalchemy.exc import IntegrityError

class EmployeeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def invite_employee(self, currentuser, payload: InviteEmployeeSchema):
        try:
            if currentuser.role.lower() not in ("owner", "admin"):
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden"
                )

            check_existing = await self.db.execute(
                select(User)
                .join(
                    CompanyMember,
                    CompanyMember.user_id == User.id
                )
                .where(
                    User.email == payload.email,
                    CompanyMember.company_id == currentuser.company_id
                )
            )

            existing_user = check_existing.scalar_one_or_none()

            if existing_user:
                raise HTTPException(
                    status_code=409,
                    detail="User already exists in this company"
                )
            temp_password = generate_random_password()

            user = User(
                name=payload.name,
                email=payload.email,
                hashed_password=hash_password(temp_password),
                must_change_password=payload.must_change_password,
            )

            self.db.add(user)
            await self.db.flush()

            member = CompanyMember(
                user_id=user.id,
                company_id=currentuser.company_id,
                role=payload.role,
                status="active",
                invited_by=currentuser.id,
            )

            self.db.add(member)

            await self.db.commit()

            await self.db.refresh(user)
            await self.db.refresh(member)

            return {
                "message": "Employee invited successfully",
                "temp_password": temp_password,
                "email": payload.email,
            }

        except HTTPException:
            await self.db.rollback()
            raise

        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="User already exists"
            )

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )

    

    async def get_employees(self,currentuser):
        try:
            result=await self.db.execute(
                select(CompanyMember)
                .join(
                    User,
                    CompanyMember.user_id == User.id
                )
                .where(
                    CompanyMember.company_id == currentuser.company_id
                )
            )
            return result.scalars().all()
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
    async def update_employee(self, currentuser,id: str,payload: InviteEmployeeSchema):
        pass

    async def delete_employee(self, currentuser,id: str):
        pass
        # if currentuser.role.lower() not in ("owner", "admin"):
        #     raise HTTPException(
        #         status_code=403,
        #         detail="Forbidden"
        #     )
        # user_to_be_deleted = await self.db.execute(select(User).join(CompanyMember).where(CompanyMember.user_id==id,CompanyMember.company_id==currentuser.company_id))
        # user_to_be_deleted = user_to_be_deleted.scalars().first()

        # if not user_to_be_deleted:
        #     raise HTTPException(
        #         status_code=404,
        #         detail="Employee not found"
        #     )
        # if currentuser.role.lower()=="admin" and user_to_be_deleted.role.lower()=="owner":
        #     raise HTTPException(
        #         status_code=403,
        #         detail="Forbidden"
        #     )
        # if user_to_be_deleted.id==currentuser.id:
        #     raise HTTPException(
        #         status_code=403,
        #         detail="Forbidden"
        #     )
        # if currentuser.role.lower()=="owner" and user_to_be_deleted.role.lower()!="owner":
        #     pass
        # try:
        #     await self.db.execute(
        #         update(CompanyMember).where(CompanyMember.user_id==id).values(status="inactive")
        #     )
        #     await self.db.commit()
        #     return {
        #         "message": "Employee deleted successfully"
        #     }
        # except Exception as e:
        #     await self.db.rollback()
        #     raise HTTPException(
        #         status_code=400,
        #         detail=str(e)
        #     )
    
           
        
    async def reset_password(self, currentuser,id: str):
        pass