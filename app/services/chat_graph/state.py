import uuid
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from app.schemas.chat import MessageRole


class RetrievedChunk(TypedDict):
    content: str
    document_id: uuid.UUID
    score: float

class LexicalChunk(TypedDict):
    content: str
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    rank: float

class Source(TypedDict):
    document_id: str
    chunk_id: str
    score: float

class History(TypedDict):
    role: MessageRole
    content: str

class ChatState(TypedDict):
    company_id: uuid.UUID
    user_id: uuid.UUID
    session_id: uuid.UUID

    question: str

    messages: Annotated[list[AnyMessage], add_messages]

    accessible_document_ids: list[uuid.UUID]
    query_embedding: list[float]
    retrieved_chunks: list[RetrievedChunk]
    lexical_chunks: list[LexicalChunk]
    fused_chunks: list[dict]
    
    conversation_history: list[History]

    answer: str
    sources: list[Source]