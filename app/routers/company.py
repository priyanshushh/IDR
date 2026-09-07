from fastapi import APIRouter,FastAPI,Depends
from app.services.company import CompanyService
from app.schemas.company import CompanyCreateSchema,CompanyUpdateSchema,CompanyResponseSchema
from app.database.dependencies import get_db

router=APIRouter()

@router.post("/",response_model=CompanyResponseSchema)
async def create_company(company:CompanyCreateSchema,db=Depends(get_db)):
    return await CompanyService().create_company(db,company)

@router.get("/list",response_model=list[CompanyResponseSchema])
async def get_company(db=Depends(get_db)):
    return await CompanyService().get_company(db)