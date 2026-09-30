"""LLM-as-judge for generation-side evaluation (build_docs/06-evaluation-
guide.md §5-§6). Every call here spends real LLM tokens — this is the
costing half of evaluation, meant to run only after retrieval-only metrics
(evals/run.py, evals/metrics.py) already look solid.

Uses structured output against a fixed rubric (decomposed per metric) rather
than a free-text "rate 1-5" prompt, so scores are consistently parseable and
each one comes with a stated reason — see the guide's §6.2 for why a rubric
beats a vibe.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

JUDGE_MODEL = "gemini-3.1-flash-lite"


class JudgeResult(BaseModel):
    faithfulness: float = Field(
        description="0.0-1.0: fraction of factual claims in ANSWER that are directly "
        "supported by CONTEXT. 1.0 only if every claim is grounded; 0.0 if none are. "
        "An answer that correctly says information isn't available makes no unsupported "
        "claims, so it should score 1.0 here regardless of correctly_abstained below."
    )
    unsupported_claims: list[str] = Field(
        default_factory=list,
        description="Specific claims in ANSWER not supported by CONTEXT, quoted "
        "verbatim. Empty list if none.",
    )
    answer_relevancy: float = Field(
        description="0.0-1.0: does ANSWER directly address QUESTION, regardless of "
        "whether it's correct? A clear, honest 'the documents don't cover that' is "
        "relevant (high score) even though it isn't an answer to the underlying fact."
    )
    context_precision: float = Field(
        description="0.0-1.0: of the numbered CONTEXT chunks, what fraction were "
        "actually useful for answering QUESTION? Low is expected and correct when "
        "QUESTION has no true answer in the documents."
    )
    context_recall: float | None = Field(
        default=None,
        description="0.0-1.0: does CONTEXT contain everything needed to fully match "
        "EXPECTED_ANSWER? Set to null when IS_UNANSWERABLE is true.",
    )
    correctly_abstained: bool | None = Field(
        default=None,
        description="Only meaningful when IS_UNANSWERABLE is true: did ANSWER "
        "correctly decline / say the information isn't available, instead of making "
        "something up? Set to null when IS_UNANSWERABLE is false.",
    )
    reasoning: str = Field(description="One or two sentences explaining the scores above.")


_JUDGE_PROMPT = """You are grading a RAG system's answer against the context it was \
given. Be strict and literal — do not give credit for claims that sound plausible but \
aren't actually stated in CONTEXT.

QUESTION:
{question}

IS_UNANSWERABLE: {is_unanswerable}
(If true, the documents don't actually contain an answer to this question — the \
correct system behavior is to decline, not to answer. Judge correctly_abstained \
instead of context_recall in that case.)

EXPECTED_ANSWER (ground truth, for reference):
{expected_answer}

CONTEXT (numbered chunks actually given to the system):
{context}

ANSWER (what the system actually said):
{answer}

Score every field in the schema against the rubric in its description."""


_judge = None


def _get_judge():
    global _judge
    if _judge is None:
        llm = ChatGoogleGenerativeAI(model=JUDGE_MODEL, temperature=0)
        _judge = llm.with_structured_output(JudgeResult)
    return _judge


async def judge_answer(
    question: str,
    expected_answer: str,
    context_chunks: list[dict],
    answer: str | None,
    is_unanswerable: bool,
) -> JudgeResult:
    context_text = "\n\n".join(
        f"[{i + 1}] {c['content']}" for i, c in enumerate(context_chunks)
    ) or "(no chunks were retrieved)"

    prompt = _JUDGE_PROMPT.format(
        question=question,
        is_unanswerable=is_unanswerable,
        expected_answer=expected_answer,
        context=context_text,
        answer=answer or "(the system did not produce a direct answer)",
    )

    return await _get_judge().ainvoke(prompt)
