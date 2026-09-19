from typing import TypedDict
import uuid


class RetrievedChunk(TypedDict):
    content: str
    document_id: uuid.UUID
    score: float

class Source(TypedDict):
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    score: float

class ChatState(TypedDict):
    question: str
    company_id: uuid.UUID
    user_id: uuid.UUID

    accessible_document_ids: list[uuid.UUID]
    query_embedding: list[float]
    retrieved_chunks: list[RetrievedChunk]    
    answer: str
    sources: list[Source]