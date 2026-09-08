from fastapi import APIRouter,FastAPI,Depends
from app.services.company import CompanyService
from app.services.auth import AuthService
from app.schemas.company import CompanyLoginSchema,CompanyUpdateSchema,CompanyResponseSchema, CompanySignupSchema
from app.database.dependencies import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_current_user, CurrentUser   

router=APIRouter()

@router.get("/list",response_model=list[CompanyResponseSchema])
async def get_company(
    currentuser: CurrentUser,
    db=Depends(get_db),
):
    """
    Get list of all companies
    """
    service = CompanyService(db)
    return await service.get_company()