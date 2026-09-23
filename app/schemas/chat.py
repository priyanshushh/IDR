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
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(BaseModel):
    user_id: uuid.UUID
    company_id: uuid.UUID
    content: str
    role: MessageRole
    id: uuid.UUID
    session_id: uuid.UUID
    sources: list[dict] | None
    created_at: datetime