from app.models.company import Company
from sqlalchemy import select
from fastapi import HTTPException
class CompanyService:
    def __init__(self):
        pass
    async def create_company(self,db,company):
        # db_company = Company(**company.dict())
        existing_company = await db.execute(
            select(Company).where(Company.name==company.name)
            )
        if existing_company.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Company already exists")
        new_company=Company(
            name=company.name,
            plan=company.plan,
            slug=company.name.replace(" ", "-").lower(),
            is_active=True
        )
        db.add(new_company)
        await db.commit()
        await db.refresh(new_company)
        return new_company

    async def get_company(self,db):
        result = await db.execute(select(Company))
        companies = result.scalars().all()
        return companies