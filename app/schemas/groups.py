from uuid import UUID
from pydantic import BaseModel, ConfigDict
from datetime import datetime
class GroupCreateRequest(BaseModel):
    group_name: str


class GroupMembersResponse(BaseModel):
    id: UUID
    name: str
    email: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class GroupResponse(BaseModel):
    id: UUID
    name: str
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID
    is_default: bool

    model_config = ConfigDict(from_attributes=True)

class GroupUpdateRequest(BaseModel):
    group_name: str
    is_default: bool

class GroupMembersRequest(BaseModel):
    group_members: list[UUID]

class GroupPermissionsRequest(BaseModel):
    document_ids: list[UUID]
