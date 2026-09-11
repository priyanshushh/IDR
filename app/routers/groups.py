from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import CurrentUser
from app.services.groups import GroupService
from app.database.dependencies import get_db
from app.schemas.groups import GroupCreateRequest, GroupResponse
router = APIRouter()


def get_group_service(
    db: AsyncSession = Depends(get_db),
) -> GroupService:
    return GroupService(db)


@router.post("/create",status_code=status.HTTP_201_CREATED,response_model=GroupResponse)
async def create_group(
    currentuser: CurrentUser,
    group_request: GroupCreateRequest,
    service: GroupService = Depends(get_group_service),
):
    return await service.create_group(
        company_id=currentuser.company_id,
        group_name=group_request.group_name,
        created_by=currentuser.id
    )

@router.get("/",response_model=list[GroupResponse])
async def get_groups(
    currentuser:CurrentUser,
    service:GroupService = Depends(get_group_service)
):
    return await service.get_groups(
        company_id=currentuser.company_id
    )