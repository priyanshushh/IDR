from pydantic import BaseModel
from enum import Enum
import uuid
from datetime import datetime

class DocumentVisibility(str, Enum):
    COMPANY_WIDE = "company_wide"
    RESTRICTED = "restricted"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentPermissionSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    group_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class DocumentSchema(BaseModel):
    id: uuid.UUID
    uploaded_by: uuid.UUID
    original_filename: str
    document_type: str
    name: str
    size_bytes: int | None = None
    is_active: bool | None = None
    company_id: uuid.UUID
    category: str
    mime_type: str
    visibility: DocumentVisibility
    status: DocumentStatus
    storage_key: str
    created_at: datetime
    source: str | None = None
    permissions: list[DocumentPermissionSchema] | None = None

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    document: DocumentSchema
    # session_id: str


class DocumentVisibilityUpdateRequest(BaseModel):
    visibility: DocumentVisibility


class DocumentUserPermissionsRequest(BaseModel):
    user_ids: list[uuid.UUID]
