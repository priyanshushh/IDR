from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.company import Company
# from app.models.employee import Employee
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy import update
from app.models.company import CompanyMember
from app.schemas.employee import InviteEmployeeSchema,UpdatedEmployee,UpdatePassword
from app.utils.generate_random_password import generate_random_password
from app.core.security import hash_password
from sqlalchemy.exc import IntegrityError
from app.core.security import verify_password,hash_password

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
                select(CompanyMember, User.name)
                .join(
                    User,
                    CompanyMember.user_id == User.id
                )
                .where(
                    CompanyMember.company_id == currentuser.company_id
                )
            )
            employees = []
            for company_member, name in result.all():
                employee = {
                    column.name: getattr(company_member, column.name)
                    for column in CompanyMember.__table__.columns
                }
                employee["name"] = name
                employees.append(employee)
            return employees
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
    async def get_employee(self,currentuser,id:str):
        try:
            result = await self.db.execute(
                select(CompanyMember, User)
                .join(
                    User,
                    CompanyMember.user_id == User.id
                )
                .where(
                    CompanyMember.user_id == id,
                    CompanyMember.company_id == currentuser.company_id
                )
            )

            row = result.first()

            if row:
                company_member, user = row

                employee = {
                    **{
                        column.name: getattr(company_member, column.name)
                        for column in CompanyMember.__table__.columns
                    },
                    **{
                        column.name: getattr(user, column.name)
                        for column in User.__table__.columns
                        if column.name != "hashed_password"
                    },
                }
            else:
                employee = None


            if not employee:
                raise HTTPException(
                    status_code=404,
                    detail="Employee not found"
                )
            
            return employee
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )

    async def update_employee(self, currentuser,id: str,payload: UpdatedEmployee):
        if currentuser.role.lower() not in ("owner", "admin"):
            raise HTTPException(
                status_code=403,
                detail="Forbidden"
            )

        check_existing = await self.db.execute(
            select(CompanyMember)
            .join(
                User,
                CompanyMember.user_id == User.id
            )
            .where(
                CompanyMember.user_id == id,
                CompanyMember.company_id == currentuser.company_id
            )
        )

        existing_user = check_existing.scalar_one_or_none()
        if not existing_user:
            raise HTTPException(
                status_code=404,
                detail="Employee not found"
            )

        
        if payload.update_key == "name":
            await self.db.execute(update(User).where(User.id==id).values(name=payload.update_key_value))
        elif payload.update_key == "email":
            await self.db.execute(update(User).where(User.id==id).values(email=payload.update_key_value))
        elif payload.update_key == "role":
            await self.db.execute(update(CompanyMember).where(CompanyMember.user_id==id).values(role=payload.update_key_value))
        elif payload.update_key == "must_change_password":
            await self.db.execute(update(User).where(User.id==id).values(must_change_password=payload.update_key_value))
        elif payload.update_key == "status":
            await self.db.execute(update(CompanyMember).where(CompanyMember.user_id==id).values(status=payload.update_key_value))
        await self.db.commit()
        
        return {
            "message": "Employee updated successfully",
            "data":{
                payload.update_key:payload.update_key_value
            }
        }

    async def delete_employee(self, currentuser,id: str):
        if currentuser.role.lower() not in ("owner", "admin"):
            raise HTTPException(
                status_code=403,
                detail="Forbidden"
            )
        user_to_be_deleted = await self.db.execute(select(User).join(CompanyMember,onclause=CompanyMember.user_id == User.id).where(CompanyMember.user_id==id,CompanyMember.company_id==currentuser.company_id))
        user_to_be_deleted = user_to_be_deleted.scalars().first()
        if not user_to_be_deleted:
            raise HTTPException(
                status_code=404,
                detail="Employee not found"
            )
        if currentuser.role.lower()=="admin" and user_to_be_deleted.role.lower()=="owner":
            raise HTTPException(
                status_code=403,
                detail="Forbidden"
            )
        if user_to_be_deleted.id==currentuser.id:
            raise HTTPException(
                status_code=403,
                detail="Forbidden"
            )
        try:
            await self.db.execute(
                update(CompanyMember).where(CompanyMember.user_id==id).values(status="inactive")
            )
            await self.db.commit()
            return {
                "message": "Employee deleted successfully"
            }
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
    
           
        
    async def reset_password(self, currentuser,id: str,payload:UpdatePassword):
        existing_user = await self.db.execute(select(User).where(User.id==id))
        user = existing_user.scalars().first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="Employee not found"
            )
        # is_admin_or_owner = currentuser.role.lower() in ["owner", "admin"]
        # is_self = id == currentuser.id
        # if not is_admin_or_owner and not is_self:
        #     raise HTTPException(
        #         status_code=403,
        #         detail="Forbidden"
        #     )

        if payload.old_password==payload.new_password:
            raise HTTPException(
                status_code=400,
                detail="Old and new passwords are same"
            )    
        if verify_password(payload.old_password,user.hashed_password) == False:
            raise HTTPException(
                status_code=400,
                detail="Old password is incorrect"
            )    
        try:
            await self.db.execute(update(User).where(User.id==id).values(hashed_password=hash_password(payload.new_password)))
            await self.db.commit()
            return {
                "message": "Password reset successfully"
            }
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
        