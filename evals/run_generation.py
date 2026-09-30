"""Generation-side evaluation harness — the second half of Stage 7 (see
build_docs/06-evaluation-guide.md §5-§6). Runs the full retrieval+generation
pipeline for each golden-dataset question and scores the actual answer with
an LLM judge: faithfulness, answer relevancy, context precision, context
recall, and (for `unanswerable` questions) whether the system correctly
declined instead of hallucinating.

Unlike evals/run.py, THIS SCRIPT SPENDS REAL LLM TOKENS — two calls per
question (one to generate the answer, one to judge it). Run evals/run.py
first and only reach for this once retrieval-only metrics already look
solid — see the guide's §9.3 build order for why.

Usage:
    python -m evals.run_generation --company-slug solstice-robotics --user-email owner@solstice.example
    python -m evals.run_generation --company-slug solstice-robotics --user-email owner@solstice.example --limit 10
    python -m evals.run_generation --company-slug solstice-robotics --user-email owner@solstice.example --category unanswerable
"""

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.services.chat_graph.full_pipeline import run_full_pipeline
from evals._common import load_company, load_user_and_role, tenant_session
from evals.judge import judge_answer
from evals.metrics import mean

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = REPO_ROOT / "build_docs" / "golden-dataset" / "golden_questions.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "evals" / "results"


MIN_SECONDS_BETWEEN_CALLS = 7.0
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 65.0

_last_call_at: float = 0.0


async def _pace() -> None:
    global _last_call_at
    loop = asyncio.get_event_loop()
    now = loop.time()
    wait = MIN_SECONDS_BETWEEN_CALLS - (now - _last_call_at)
    if wait > 0:
        await asyncio.sleep(wait)
    _last_call_at = loop.time()


async def _with_retries(coro_fn, /, *args, **kwargs):
    last_exc: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return await coro_fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            # Google's 429 body names which quota was hit.
            if "PerDay" in str(exc):
                print(
                    f"    (error: {exc!r})\n"
                    "    This looks like a DAILY quota cap, not a transient rate "
                    "limit — not retrying. Try again after the quota resets "
                    "(often midnight Pacific for Gemini's free tier), or point "
                    "JUDGE_MODEL/nodes.py's model at a different quota bucket."
                )
                raise
            if attempt < RETRY_ATTEMPTS - 1:
                print(
                    f"    (error: {exc!r} — waiting {RETRY_DELAY_SECONDS:.0f}s "
                    "for the per-minute quota to reset)"
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)
    raise last_exc


def _fmt(value) -> str:
    if value is None:
        return "  -  "
    return f"{value:0.3f}"


def _aggregate(records: list[dict]) -> dict:
    if not records:
        return {}

    answerable = [r for r in records if not r["is_unanswerable"]]
    unanswerable = [r for r in records if r["is_unanswerable"]]

    agg = {
        "faithfulness": mean([r["judge"]["faithfulness"] for r in records]),
        "answer_relevancy": mean([r["judge"]["answer_relevancy"] for r in records]),
        "context_precision": mean([r["judge"]["context_precision"] for r in records]),
        "context_recall": (
            mean([r["judge"]["context_recall"] for r in answerable]) if answerable else None
        ),
    }

    if unanswerable:
        abstain_values = [
            1.0 if r["judge"]["correctly_abstained"] else 0.0
            for r in unanswerable
            if r["judge"]["correctly_abstained"] is not None
        ]
        agg["correct_abstention_rate"] = mean(abstain_values) if abstain_values else None

    return agg


def _print_aggregate(title: str, agg: dict) -> None:
    print(f"\n{title}")
    for key, value in agg.items():
        print(f"  {key:<24} {_fmt(value)}")


async def run_eval(
    company_slug: str,
    user_email: str,
    dataset_path: Path,
    output_dir: Path,
    category_filter: str | None,
    limit: int | None,
) -> None:
    company = await load_company(company_slug)
    user, role = await load_user_and_role(user_email, company.id)

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    questions = dataset["questions"]
    if category_filter:
        questions = [q for q in questions if q["category"] == category_filter]
    if limit:
        questions = questions[:limit]

    if not questions:
        raise SystemExit("No questions to run (check --category / --limit).")

    print(f"Company: {company.name} ({company.slug})")
    print(f"User: {user.email} (role={role})")
    print(f"Dataset: {dataset_path} — {len(questions)} question(s) selected")
    est_minutes = (len(questions) * 2 * MIN_SECONDS_BETWEEN_CALLS) / 60
    print(
        f"This will make ~{len(questions) * 2} LLM calls "
        f"({len(questions)} generation + {len(questions)} judge), paced at "
        f"1 every {MIN_SECONDS_BETWEEN_CALLS:.0f}s for the free-tier quota — "
        f"roughly {est_minutes:.0f} min minimum, longer if any 429s hit. "
        "Use --limit/--category to run a smaller batch first."
    )

    records: list[dict] = []
    tool_call_question_ids: list[str] = []

    async with tenant_session(company.schema_name) as db:
        for question in questions:
            is_unanswerable = question["category"] == "unanswerable"

            await _pace()
            pipeline_result = await _with_retries(
                run_full_pipeline, db, company.id, user.id, question["question"]
            )

            if pipeline_result["tool_called"] or pipeline_result["answer"] is None:
                tool_call_question_ids.append(question["id"])
                print(f"  SKIPPED {question['id']} — model called a tool instead of answering")
                continue

            await _pace()
            judge_result = await _with_retries(
                judge_answer,
                question=question["question"],
                expected_answer=question["expected_answer"],
                context_chunks=pipeline_result["context_chunks"],
                answer=pipeline_result["answer"],
                is_unanswerable=is_unanswerable,
            )

            records.append(
                {
                    "id": question["id"],
                    "category": question["category"],
                    "difficulty": question.get("difficulty"),
                    "question": question["question"],
                    "expected_answer": question["expected_answer"],
                    "is_unanswerable": is_unanswerable,
                    "generated_answer": pipeline_result["answer"],
                    "context_chunk_count": len(pipeline_result["context_chunks"]),
                    "judge": judge_result.model_dump(),
                }
            )
            print(f"  scored {question['id']} ({question['category']})")

    if tool_call_question_ids:
        print(
            f"\nWARNING: {len(tool_call_question_ids)} question(s) triggered a tool call "
            f"instead of a direct answer and were skipped from scoring: "
            f"{tool_call_question_ids}"
        )

    by_category: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_category[record["category"]].append(record)

    report_aggregates: dict[str, dict] = {"overall": _aggregate(records)}
    _print_aggregate("=== OVERALL ===", report_aggregates["overall"])

    for category, cat_records in sorted(by_category.items()):
        agg = _aggregate(cat_records)
        report_aggregates[category] = agg
        _print_aggregate(f"--- category: {category} (n={len(cat_records)}) ---", agg)

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"gen__{timestamp}__{company_slug}.json"
    output_path.write_text(
        json.dumps(
            {
                "run_at": timestamp,
                "company_slug": company_slug,
                "user_email": user_email,
                "dataset_path": str(dataset_path),
                "category_filter": category_filter,
                "question_count": len(records),
                "tool_call_skipped": tool_call_question_ids,
                "aggregates": report_aggregates,
                "records": records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved full results to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-slug", required=True, help="company.slug of the test tenant")
    parser.add_argument(
        "--user-email",
        required=True,
        help="email of a member of that company (their accessible-document set is used)",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--category",
        default=None,
        choices=["factual", "numeric", "paraphrase", "multi_hop", "unanswerable"],
        help="only run questions in this category",
    )
    parser.add_argument("--limit", type=int, default=None, help="only run the first N selected questions")
    args = parser.parse_args()

    asyncio.run(
        run_eval(
            company_slug=args.company_slug,
            user_email=args.user_email,
            dataset_path=args.dataset,
            output_dir=args.output_dir,
            category_filter=args.category,
            limit=args.limit,
        )
    )


if __name__ == "__main__":
    main()
