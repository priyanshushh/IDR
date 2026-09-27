from sentence_transformers import CrossEncoder

_reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank(query: str, chunks: list[dict]) -> list[dict]:
    pairs = [(query, c["content"]) for c in chunks]
    scores = _reranker.predict(pairs)
    for c, s in zip(chunks, scores):
        c["rerank_score"] = float(s)
    return sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)