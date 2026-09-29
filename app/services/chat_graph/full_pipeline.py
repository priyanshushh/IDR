"""Runs retrieval + generation for a single question using the same node
functions the live chat graph uses, without touching ChatSession/ChatMessage
persistence and without needing a session_id.

This is the counterpart to app/services/chat_graph/debug.py: debug.py stops
before generation (no LLM call, free to run repeatedly); this module goes all
the way through generate_answer (one real LLM call). Used by
evals/run_generation.py to get a real answer to score with an LLM judge — see
build_docs/06-evaluation-guide.md §5.
"""

import uuid

from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat_graph.nodes import make_nodes


async def run_full_pipeline(
    db: AsyncSession,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    question: str,
) -> dict:
    nodes = make_nodes(db)
    state: dict = {
        "company_id": company_id,
        "user_id": user_id,
        "question": question,
        "messages": [HumanMessage(content=question)],
        "conversation_history": [],
    }

    state.update(await nodes["resolve_permissions"](state))
    state.update(await nodes["embed_question"](state))
    state.update(await nodes["retrieve_chunks"](state))
    state.update(await nodes["retrieve_lexical"](state))
    state.update(await nodes["fuse_results"](state))
    state.update(await nodes["rerank_chunks"](state))

    # Snapshot before generate_answer runs — same reasoning as debug.py's
    # _to_debug_chunk: state["retrieved_chunks"] is what actually goes into
    # the prompt, and nothing mutates it further after this point, but the
    # dicts themselves stay owned by chat_graph rather than eval code.
    context_chunks = [
        {
            "chunk_id": str(c["chunk_id"]),
            "document_id": str(c["document_id"]),
            "content": c["content"],
        }
        for c in state["retrieved_chunks"]
    ]

    result = await nodes["generate_answer"](state)

    # generate_answer only sets "answer"/"sources" when the LLM didn't call a
    # tool (see nodes.py) — our questions are all company-internal, so this
    # should be rare, but the caller needs to know it happened rather than
    # silently scoring a missing answer.
    response_messages = result.get("messages") or []
    tool_called = bool(response_messages) and bool(
        getattr(response_messages[0], "tool_calls", None)
    )

    return {
        "question": question,
        "answer": result.get("answer"),
        "sources": result.get("sources", []),
        "context_chunks": context_chunks,
        "tool_called": tool_called,
    }
