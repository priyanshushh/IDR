from typing import TypedDict
import uuid
from app.schemas.chat import MessageRole

class RetrievedChunk(TypedDict):
    content: str
    document_id: uuid.UUID
    score: float

class Source(TypedDict):
    document_id: str
    chunk_id: str
    score: float

class History(TypedDict):
    role: MessageRole
    content: str

class ChatState(TypedDict):
    question: str
    company_id: uuid.UUID
    user_id: uuid.UUID
    session_id: uuid.UUID
    conversation_history: list[History]

    accessible_document_ids: list[uuid.UUID]
    query_embedding: list[float]
    retrieved_chunks: list[RetrievedChunk]    
    answer: str
    sources: list[Source]
    