import asyncio
import logging

from sqlalchemy import select, func, desc, Text
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
from langchain_core.runnables import RunnableConfig
from app.services.reranker import rerank
from app.services.guardrails import scan_for_injection

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.6
TOP_K = 8
HISTORY_LIMIT = 10
RRF_K = 60

# Guardrail (build_docs/08-observability-and-guardrails.md §2.4): without this,
# generate_answer <-> tools has no cap of its own and relies entirely on LangGraph's
# default recursion_limit — if ever hit, that surfaces as a raw GraphRecursionError
# instead of a usable answer.
MAX_TOOL_CALLS = 3

HEDGE_PHRASES = ("don't have information", "not available", "couldn't find", "no information")

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

    # "gemini-flash-latest" (-> gemini-3.8-flash) hit a real 20-req/day cap
    # while building evals/run_generation.py, and gemini-2.5-flash — despite
    # being listed by client.models.list() for this key — 404s as "no longer
    # available to new users" (a known Gemini API inconsistency: the list
    # endpoint doesn't reflect per-key callability). gemini-flash-lite-latest
    # is confirmed listed AND on a separate, more generous free-tier quota
    # bucket than the full "flash" tier. Re-verify with
    # `client.models.list()` (google.genai) before changing this again —
    # don't guess a name from memory, this catalog churns fast.
    llm = ChatGoogleGenerativeAI(model="gemini-flash-lite-latest")
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
        for c in chunks:
            hits = scan_for_injection(c["content"])
            if hits:
                logger.warning(
                    "possible prompt injection in chunk_id=%s patterns=%s",
                    c["chunk_id"], hits,
                )
        return {"retrieved_chunks": chunks}

    async def retrieve_lexical(state: ChatState) -> dict:
        if not state["accessible_document_ids"]:
            return {"lexical_chunks": []}

        # websearch_to_tsquery ANDs every remaining term together by default
        # (e.g. "What databases does this candidate use?" -> 'databas' & 'candid' & 'us'),
        # which almost never matches a full sentence of content. Rewrite the AND into an
        # OR so a chunk matches if it contains *any* of the question's keywords, and let
        # ts_rank_cd / RRF fusion do the relevance ordering instead.
        base_tsquery = func.websearch_to_tsquery("english", state["question"])
        tsquery = func.to_tsquery("english", func.replace(func.cast(base_tsquery, Text), " & ", " | "))
        rank = func.ts_rank_cd(DocumentChunks.content_tsv, tsquery).label("rank")

        stmt = (
            select(DocumentChunks, rank)
            .where(DocumentChunks.document_id.in_(state["accessible_document_ids"]))
            .where(DocumentChunks.content_tsv.op("@@")(tsquery))
            .order_by(desc("rank"))
            .limit(TOP_K)
        )
        result = await db.execute(stmt)
        chunks = [
            {"content": c.content, "document_id": c.document_id, "chunk_id": c.id, "rank": rank}
            for c, rank in result.all()
        ]
        for c in chunks:
            hits = scan_for_injection(c["content"])
            if hits:
                logger.warning(
                    "possible prompt injection in chunk_id=%s patterns=%s",
                    c["chunk_id"], hits,
                )
        return {"lexical_chunks": chunks}

    def reciprocal_rank_fusion(*ranked_lists: list[dict], key="chunk_id") -> list[dict]:
        scores: dict[str, float] = {}
        items: dict[str, dict] = {}

        for ranked in ranked_lists:
            for rank, item in enumerate(ranked):
                item_id = str(item[key])
                scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (RRF_K + rank + 1)
                items[item_id] = item

        fused_ids = sorted(scores, key=lambda i: scores[i], reverse=True)

        # Stamp the fused score onto each item (same in-place-mutation pattern
        # rerank() already uses for rerank_score) so debug/eval tooling
        # (app/services/chat_graph/debug.py) can report it without having to
        # recompute RRF itself.
        fused = []
        for item_id in fused_ids:
            item = items[item_id]
            item["rrf_score"] = scores[item_id]
            fused.append(item)
        return fused


    async def fuse_results(state: ChatState) -> dict:
        fused = reciprocal_rank_fusion(state["retrieved_chunks"], state["lexical_chunks"])
        return {"fused_chunks": fused[:TOP_K * 2]}
    
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

    async def rerank_chunks(state: ChatState) -> dict:
        if not state["fused_chunks"]:
            return {"retrieved_chunks": []}
        reranked = await asyncio.to_thread(rerank, state["question"], state["fused_chunks"])
        return {"retrieved_chunks": reranked[:TOP_K]}


    async def generate_answer(state: ChatState, config: RunnableConfig) -> dict:
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

        # Guardrail: once the cap is hit, call the plain (tool-less) llm instead of
        # llm_with_tools — the model can't request another tool call, so it's
        # forced to answer with whatever it already has instead of looping further.
        tool_call_count = state.get("tool_call_count", 0)
        model = llm if tool_call_count >= MAX_TOOL_CALLS else llm_with_tools
        response = await model.ainvoke(messages, config=config)

        usage_metadata = response.usage_metadata or {}
        usage = dict(state.get("usage") or {})
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            usage[key] = usage.get(key, 0) + (usage_metadata.get(key) or 0)

        result = {
            "messages": [response],
            "tool_call_count": tool_call_count + bool(response.tool_calls),
            "usage": usage,
        }

        if not response.tool_calls:
            answer = extract_text(response.content)

            if scan_for_injection(answer):
                logger.warning(
                    "model output matched injection patterns, session_id=%s",
                    state["session_id"],
                )

            if not state["retrieved_chunks"] and not any(
                p in answer.lower() for p in HEDGE_PHRASES
            ):
                logger.warning(
                    "possible ungrounded answer with no context, session_id=%s",
                    state["session_id"],
                )

            result["answer"] = answer

            result["sources"] = [
                {
                    "document_id": str(c["document_id"]),
                    "chunk_id": str(c["chunk_id"]),
                    "score": c.get("rerank_score"),
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
        "retrieve_lexical": retrieve_lexical,
        "fuse_results": fuse_results,
        "rerank_chunks": rerank_chunks,
        "generate_answer": generate_answer,
    }