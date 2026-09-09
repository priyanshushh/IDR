from fastapi import APIRouter, Depends, status
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.dependencies import get_db
from app.core.security import CurrentUser
from app.schemas.employee import InviteEmployeeSchema, UpdatedEmployee, UpdatePassword
from app.services.employee import EmployeeService

router = APIRouter()

@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_employee(
    currentuser: CurrentUser,
    payload: InviteEmployeeSchema,
    db: AsyncSession = Depends(get_db),
):
    service = EmployeeService(db)
    return await service.invite_employee(currentuser, payload)

@router.get("/", status_code=status.HTTP_200_OK)
async def get_employees(currentuser:CurrentUser,db:AsyncSession=Depends(get_db)):
    service=EmployeeService(db)
    return await service.get_employees(currentuser)

@router.get("/{id}", status_code=status.HTTP_200_OK)
async def get_employee(
    currentuser: CurrentUser,
    id: str,
    db: AsyncSession = Depends(get_db),
):
    service = EmployeeService(db)
    return await service.get_employee(currentuser, id)

@router.patch("/{id}", status_code=status.HTTP_200_OK)
async def update_employee(
    currentuser: CurrentUser,
    id: str,
    payload: UpdatedEmployee,
    db: AsyncSession = Depends(get_db),
):
    service = EmployeeService(db)
    return await service.update_employee(currentuser, id, payload)

@router.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_employee(
    currentuser: CurrentUser,
    id: str,
    db: AsyncSession = Depends(get_db),
):
    service = EmployeeService(db)
    return await service.delete_employee(currentuser, id)

@router.post("/{id}/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    currentuser: CurrentUser,
    payload:UpdatePassword,
    id: str,
    db: AsyncSession = Depends(get_db),
):  
    service = EmployeeService(db)
    return await service.reset_password(currentuser, id, payload)