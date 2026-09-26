import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import DocumentChunks
from app.services.embeddings import embed_query
from app.services.permissions import resolve_accessible_document_ids
from app.services.chat_graph.state import ChatState
from langchain_google_genai import ChatGoogleGenerativeAI
from app.models.chat import ChatMessage
from app.services.prompts.system_prompt import SYSTEM_PROMPT
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_core.messages import SystemMessage

SIMILARITY_THRESHOLD = 0.8
TOP_K = 8
HISTORY_LIMIT = 10

def extract_text(content) -> str:
    """Normalize LangChain/Gemini message content to plain text."""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []

        for item in content:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))

        return "".join(texts)

    return str(content)


def make_nodes(db: AsyncSession):
    """Nodes close over the request's tenant-scoped `db` session (same pattern as
    DocumentService/ChatService — one session per request, not a global)."""

    llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
    web_search_tool = DuckDuckGoSearchResults(num_results=3, max_results=3)
    tools = [web_search_tool]
    llm_with_tools = llm.bind_tools(tools)

    async def resolve_permissions(state: ChatState) -> dict:
        ids = await resolve_accessible_document_ids(
            db, state["company_id"], state["user_id"]
        )
        return {"accessible_document_ids": ids}

    async def embed_question(state: ChatState) -> dict:
        vector = await asyncio.to_thread(embed_query, state["question"])
        return {"query_embedding": vector}

    async def retrieve_chunks(state: ChatState) -> dict:
        if not state["accessible_document_ids"]:
            return {"retrieved_chunks": []}

        stmt = (
            select(
                DocumentChunks,
                DocumentChunks.embedding.cosine_distance(state["query_embedding"]).label(
                    "distance"
                ),
            )
            .where(DocumentChunks.document_id.in_(state["accessible_document_ids"]))
            .order_by("distance")
            .limit(TOP_K)
        )
        result = await db.execute(stmt)
        chunks = [
            {
                "content": chunk.content,
                "document_id": chunk.document_id,
                "chunk_id": chunk.id,
                "score": distance,
            }
            for chunk, distance in result.all()
            if distance <= SIMILARITY_THRESHOLD
        ]
        return {"retrieved_chunks": chunks}
        
    async def load_history(state:ChatState) -> dict:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == state["session_id"])
            .order_by(ChatMessage.created_at.desc())
            .limit(HISTORY_LIMIT)
        )
        result = await db.execute(stmt)
        rows = list(reversed(result.scalars().all()))
        return {
            "conversation_history": [
                {"role": row.role, "content": row.content} for row in rows
            ]
        }
    
    async def generate_answer(state: ChatState) -> dict:
        context = "\n\n".join(
            f"[{i + 1}] {c['content']}"
            for i, c in enumerate(state["retrieved_chunks"])
        )

        history_text = "\n".join(
            f"{turn['role']}: {turn['content']}"
            for turn in state["conversation_history"]
        )

        prompt = SYSTEM_PROMPT.format(
            history_text=history_text,
            context=context,
            question=state["question"],
        )

        messages = [
            SystemMessage(content=prompt),
            *state["messages"],
        ]

        response = await llm_with_tools.ainvoke(messages)

        result = {
            "messages": [response],
        }

        if not response.tool_calls:
            answer = extract_text(response.content)

            result["answer"] = answer

            result["sources"] = [
                {
                    "document_id": str(c["document_id"]),
                    "chunk_id": str(c["chunk_id"]),
                    "score": c["score"],
                }
                for c in state["retrieved_chunks"]
            ]

        return result

    return {
        "tools": tools,
        "resolve_permissions": resolve_permissions,
        "embed_question": embed_question,
        "retrieve_chunks": retrieve_chunks,
        "load_history": load_history,
        "generate_answer": generate_answer,
    }