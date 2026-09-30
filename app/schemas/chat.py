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


class RetrievalDebugRequest(BaseModel):
    question: str


class RetrievalDebugChunk(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    score: float | None
    score_type: str


class RetrievalDebugResponse(BaseModel):
    question: str
    accessible_document_count: int
    vector_only: list[RetrievalDebugChunk]
    lexical_only: list[RetrievalDebugChunk]
    fused: list[RetrievalDebugChunk]
    reranked: list[RetrievalDebugChunk]

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