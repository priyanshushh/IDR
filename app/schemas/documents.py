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
    permissions: list[str] | None = None


    
class DocumentUploadResponse(BaseModel):
    document: DocumentSchema
    session_id: str
