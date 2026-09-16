from pydantic import BaseModel
from enum import Enum

class DocumentVisibility(str, Enum):
    COMPANY_WIDE = "company_wide"
    RESTRICTED = "restricted"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
