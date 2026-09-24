from enum import Enum
from pydantic import BaseModel
import uuid
from datetime import datetime

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ChatQueryRequest(BaseModel):
    query: str
    

class ChatQueryResponse(BaseModel):
    answer: str
    sources: list[dict]

class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    title:str
    user_id: uuid.UUID
    company_id:uuid.UUID
    document_ids:list[str] | None
    created_at: datetime

    model_config = {
        "from_attributes":True
    }


class ChatMessageResponse(BaseModel):
    user_id: uuid.UUID
    company_id: uuid.UUID
    content: str
    role: MessageRole
    id: uuid.UUID
    session_id: uuid.UUID
    sources: list[dict] | None
    created_at: datetime

    model_config = {
        "from_attributes":True
    }