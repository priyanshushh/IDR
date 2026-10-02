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

    # Guardrail: caps the generate_answer <-> tools round-trip (see MAX_TOOL_CALLS
    # in nodes.py) so a model that keeps requesting searches can't loop past
    # LangGraph's recursion_limit into a raw GraphRecursionError.
    tool_call_count: int

    # Accumulated across every LLM call this request made (the tool-calling loop
    # can call the model more than once) — input_tokens/output_tokens/total_tokens.
    usage: dict