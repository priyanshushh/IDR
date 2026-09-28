import math


def dedupe_preserve_order(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item_id in ids:
        if item_id not in seen:
            seen.add(item_id)
            deduped.append(item_id)
    return deduped


def recall_at_k(ranked_ids: list[str], relevant_ids: set[str]) -> float | None:
    """Of all relevant documents, what fraction did we surface at all?
    None (not 0.0) when there's nothing relevant to find — that case isn't a
    retrieval failure, it's a different question entirely (see abstention
    metrics in evals/run.py for the unanswerable category).
    """
    if not relevant_ids:
        return None
    found = len(set(ranked_ids) & relevant_ids)
    return found / len(relevant_ids)


def precision_at_k(ranked_ids: list[str], relevant_ids: set[str]) -> float | None:
    """Of what we returned, how much was actually relevant?"""
    if not ranked_ids:
        return None
    found = len(set(ranked_ids) & relevant_ids)
    return found / len(ranked_ids)


def reciprocal_rank(ranked_ids: list[str], relevant_ids: set[str]) -> float:
    """1 / (position of the first relevant hit), 0.0 if none found. Average
    this across questions to get MRR.
    """
    if not relevant_ids:
        return 0.0
    for position, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / position
    return 0.0


def ndcg_at_k(ranked_ids: list[str], relevant_ids: set[str]) -> float | None:
    """Rewards having ALL relevant documents ranked high, not just the first
    one (that's what reciprocal_rank alone would miss on multi-hop questions).
    Binary relevance (a document is either relevant or it isn't — no partial
    credit), normalized against the best possible ordering for this question.
    """
    if not relevant_ids:
        return None

    dcg = 0.0
    for position, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant_ids:
            dcg += 1.0 / math.log2(position + 1)

    ideal_hits = min(len(relevant_ids), len(ranked_ids))
    idcg = sum(1.0 / math.log2(position + 1) for position in range(1, ideal_hits + 1))

    if idcg == 0:
        return 0.0
    return dcg / idcg


def mean(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)
