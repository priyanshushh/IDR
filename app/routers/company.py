from fastapi import APIRouter,FastAPI,Depends
from app.services.company import CompanyService
from app.services.auth import AuthService
from app.schemas.company import CompanyLoginSchema,CompanyUpdateSchema,CompanyResponseSchema, CompanySignupSchema
from app.database.dependencies import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router=APIRouter()

@router.post("/signup")
async def signup_company(
    payload: CompanySignupSchema,
    db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    return await service.signup_company(payload)
    
@router.post("/signin")
async def signin(
    payload: CompanyLoginSchema,
    db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    return await service.signin(payload)

@router.post("/refresh")
async def refresh(
    raw_refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    return await service.refresh(raw_refresh_token)

@router.get("/list",response_model=list[CompanyResponseSchema])
async def get_company(db=Depends(get_db)):
    service = CompanyService(db)
    return await service.get_company()