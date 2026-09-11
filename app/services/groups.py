from app.models.groups import Group
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
class GroupService:
    def __init__(
        self,
        db: AsyncSession,
    ):
        self.db = db

    async def create_group(
        self,
        company_id,
        group_name,
        created_by
    ):  
        try:
            stmt = (
                select(Group)
                .where(Group.company_id == company_id)
                .where(Group.name == group_name)
            )

            result = await self.db.execute(stmt)
            existing_group = result.scalars().first()
            if existing_group:
                raise HTTPException(status_code=400, detail="Group already exists")

            group = Group(
            company_id=company_id,
            name=group_name,
            is_default=False,
            created_by=created_by,
            updated_by=created_by
            )
            self.db.add(group)
            await self.db.commit()
            await self.db.refresh(group)
            return group
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_groups(
        self,
        company_id
    ):
        try:
            stmt = (
                select(Group)
                .where(Group.company_id == company_id)
            )
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))