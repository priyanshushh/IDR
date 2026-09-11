from uuid import UUID
from pydantic import BaseModel, ConfigDict
from datetime import datetime
class GroupCreateRequest(BaseModel):
    group_name: str


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
