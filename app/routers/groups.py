from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import CurrentUser
from app.core.tenant_db import get_tenant_db
from app.services.groups import GroupService
from app.schemas.groups import GroupCreateRequest, GroupResponse, GroupUpdateRequest, GroupMembersRequest, GroupPermissionsRequest,GroupMembersResponse
import uuid

router = APIRouter()


def get_group_service(
    db: AsyncSession = Depends(get_tenant_db),
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

@router.patch("/{group_id}",response_model=GroupResponse)
async def update_group(
    currentuser:CurrentUser,
    group_id:uuid.UUID,
    group_request:GroupUpdateRequest,
    service:GroupService = Depends(get_group_service)
):  
    return await service.update_group(
        company_id=currentuser.company_id,
        group_id=group_id,
        group_name=group_request.group_name,
        is_default=group_request.is_default,
        updated_by=currentuser.id
    )

@router.delete("/{group_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    currentuser:CurrentUser,
    group_id:uuid.UUID,
    service:GroupService = Depends(get_group_service)
):
    await service.delete_group(
        company_id=currentuser.company_id,
        group_id=group_id,
        updated_by=currentuser.id
    )

@router.post("/{group_id}/members",response_model=GroupResponse)
async def add_group_members(
    currentuser:CurrentUser,
    group_id:uuid.UUID,
    group_members_request:GroupMembersRequest,
    service:GroupService = Depends(get_group_service)
):
    return await service.add_group_members(
        company_id=currentuser.company_id,
        group_id=group_id,
        group_members=group_members_request.group_members,
        updated_by=currentuser.id
    )


@router.delete("/{group_id}/members/{user_id}",status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(
    currentuser:CurrentUser,
    group_id:uuid.UUID,
    user_id:uuid.UUID,
    service:GroupService = Depends(get_group_service)
):
    await service.remove_group_member(
        company_id=currentuser.company_id,
        group_id=group_id,
        user_id=user_id,
        updated_by=currentuser.id
    )

@router.patch("/{group_id}/permissions")
async def update_group_permissions(
    currentuser:CurrentUser,
    group_id:uuid.UUID,
    group_permissions_request:GroupPermissionsRequest,
    service:GroupService = Depends(get_group_service)
):
    return await service.update_group_permissions(
        company_id=currentuser.company_id,
        group_id=group_id,
        document_ids=group_permissions_request.document_ids,
        updated_by=currentuser.id
    )

@router.get("/{group_id}/members",response_model=list[GroupMembersResponse])
async def get_group_members(
    currentuser:CurrentUser,
    group_id:uuid.UUID,
    service:GroupService = Depends(get_group_service)
):
    return await service.get_group_members(
        company_id=currentuser.company_id,
        group_id=group_id
    )