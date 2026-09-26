from typing import TypedDict
import uuid
from app.schemas.chat import MessageRole

from typing import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from typing_extensions import TypedDict


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
    company_id: str
    user_id: str
    session_id: str

    question: str

    messages: Annotated[list, add_messages]

    accessible_document_ids: list
    query_embedding: list
    retrieved_chunks: list

    conversation_history: list

    answer: str
    sources: list

    web_context: str
    