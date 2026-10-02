import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.chat_graph.nodes import make_nodes


def _to_debug_chunk(chunk: dict, score_field: str, score_type: str) -> dict:
    return {
        "chunk_id": str(chunk["chunk_id"]),
        "document_id": str(chunk["document_id"]),
        "content": chunk["content"],
        "score": chunk.get(score_field),
        "score_type": score_type,
    }


async def run_retrieval_debug(
    db: AsyncSession,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    question: str,
    role: str,
) -> dict:
    nodes = make_nodes(db)
    state: dict = {"company_id": company_id, "user_id": user_id, "question": question, "role": role}

    state.update(await nodes["resolve_permissions"](state))
    state.update(await nodes["embed_question"](state))

    state.update(await nodes["retrieve_chunks"](state))
    
    
    vector_only = [
        _to_debug_chunk(c, "score", "cosine_distance") for c in state["retrieved_chunks"]
    ]

    state.update(await nodes["retrieve_lexical"](state))
    lexical_only = [
        _to_debug_chunk(c, "rank", "ts_rank_cd") for c in state["lexical_chunks"]
    ]

    state.update(await nodes["fuse_results"](state))
    fused = [_to_debug_chunk(c, "rrf_score", "rrf") for c in state["fused_chunks"]]

    state.update(await nodes["rerank_chunks"](state))
    reranked = [
        _to_debug_chunk(c, "rerank_score", "cross_encoder")
        for c in state["retrieved_chunks"]
    ]

    return {
        "question": question,
        "accessible_document_count": len(state.get("accessible_document_ids", [])),
        "vector_only": vector_only,
        "lexical_only": lexical_only,
        "fused": fused,
        "reranked": reranked,
    }
