from fastapi import APIRouter,FastAPI,Depends
from app.services.auth import AuthService
from app.schemas.company import CompanySignupSchema
from app.database.dependencies import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from app.core.security import CurrentUser
from fastapi.security import OAuth2PasswordRequestForm


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
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)

    return await service.signin(
        email=form_data.username,
        password=form_data.password,
    )

@router.post("/refresh-token")
async def refresh(
    raw_refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    return await service.refresh(raw_refresh_token)

@router.get("/me")
async def me(
    currentuser: CurrentUser
):
    return currentuser

@router.post("/logout")
async def logout(
    currentuser: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.logout(currentuser)