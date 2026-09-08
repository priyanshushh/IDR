from app.models.company import Company
from sqlalchemy import select
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

class CompanyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_company(self):
        result = await self.db.execute(select(Company))
        companies = result.scalars().all()
        return companies