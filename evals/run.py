

"""Retrieval-only evaluation harness 


Usage:
    python -m evals.run --company-slug solstice-robotics --user-email owner@solstice.example
    python -m evals.run --company-slug solstice-robotics --user-email owner@solstice.example --category multi_hop
    python -m evals.run --company-slug solstice-robotics --user-email owner@solstice.example --limit 10
"""
import argparse
import asyncio
import json
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import event, select
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession

from app.database.database import AsyncSessionLocal, TENANT_SCHEMA
from app.models.company import Company, CompanyMember
from app.models.documents import Document
from app.models.user import User
from app.services.chat_graph.debug import run_retrieval_debug
from evals.metrics import (
    dedupe_preserve_order,
    mean,
    ndcg_at_k,
    precision_at_k,
    reciprocal_rank,
    recall_at_k,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = REPO_ROOT / "build_docs" / "golden-dataset" / "golden_questions.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "evals" / "results"

STAGES = ["vector_only", "lexical_only", "fused", "reranked"]


@asynccontextmanager
async def _tenant_session(schema_name: str):
    """Same schema_translate_map pattern as app/core/tenant_db.py, without the
    FastAPI Depends(CurrentUser) plumbing this CLI script doesn't have.
    """
    async with AsyncSessionLocal() as session:
        schema_translate_map = {TENANT_SCHEMA: schema_name}

        @event.listens_for(session.sync_session, "after_begin")
        def _apply_schema_translate_map(
            sync_session: SyncSession, transaction, connection: Connection
        ) -> None:
            connection.execution_options(schema_translate_map=schema_translate_map)

        yield session


async def _load_company(slug: str) -> Company:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Company).where(Company.slug == slug))
        company = result.scalar_one_or_none()

    if company is None:
        raise SystemExit(
            f"No company found with slug={slug!r}. Sign up the test company through "
            "the app first (see build_docs/golden-dataset/README.md)."
        )
    if not company.schema_name:
        raise SystemExit(f"Company {slug!r} has no schema_name provisioned yet.")
    return company


async def _load_user_and_role(email: str, company_id) -> tuple[User, str]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User, CompanyMember.role)
            .join(CompanyMember, CompanyMember.user_id == User.id)
            .where(User.email == email, CompanyMember.company_id == company_id)
        )
        row = result.first()

    if row is None:
        raise SystemExit(
            f"No user with email={email!r} belonging to this company was found."
        )
    return row[0], row[1]


async def _load_filename_map(db: AsyncSession, company_id) -> dict[str, str]:
    result = await db.execute(
        select(Document.original_filename, Document.id).where(
            Document.company_id == company_id
        )
    )
    return {filename: str(doc_id) for filename, doc_id in result.all()}


def _relevant_ids_for(question: dict, filename_map: dict[str, str]) -> tuple[set[str], list[str]]:
    """Returns (relevant document ids, filenames that couldn't be matched)."""
    expected = question.get("expected_source_document") or []
    relevant_ids: set[str] = set()
    missing: list[str] = []
    for filename in expected:
        doc_id = filename_map.get(filename)
        if doc_id is None:
            missing.append(filename)
        else:
            relevant_ids.add(doc_id)
    return relevant_ids, missing


def _score_stage(ranked_doc_ids: list[str], relevant_ids: set[str], is_unanswerable: bool) -> dict:
    if is_unanswerable:
        return {"empty_result": len(ranked_doc_ids) == 0}
    return {
        "recall": recall_at_k(ranked_doc_ids, relevant_ids),
        "precision": precision_at_k(ranked_doc_ids, relevant_ids),
        "reciprocal_rank": reciprocal_rank(ranked_doc_ids, relevant_ids),
        "ndcg": ndcg_at_k(ranked_doc_ids, relevant_ids),
    }


def _aggregate(rows: list[dict], is_unanswerable: bool) -> dict:
    if is_unanswerable:
        return {"empty_result_rate": mean([1.0 if r["empty_result"] else 0.0 for r in rows])}
    return {
        "recall": mean([r["recall"] for r in rows]),
        "precision": mean([r["precision"] for r in rows]),
        "mrr": mean([r["reciprocal_rank"] for r in rows]),
        "ndcg": mean([r["ndcg"] for r in rows]),
    }


def _fmt(value) -> str:
    if value is None:
        return "   -  "
    return f"{value:0.3f}"


def _print_stage_table(title: str, per_stage_rows: dict[str, list[dict]], is_unanswerable: bool) -> dict:
    print(f"\n{title}")
    if is_unanswerable:
        header = f"{'stage':<14} {'empty_result_rate':>18}"
        print(header)
        print("-" * len(header))
        aggregates = {}
        for stage in STAGES:
            agg = _aggregate(per_stage_rows[stage], is_unanswerable=True)
            aggregates[stage] = agg
            print(f"{stage:<14} {_fmt(agg['empty_result_rate']):>18}")
        return aggregates

    header = f"{'stage':<14} {'recall':>8} {'precision':>10} {'mrr':>8} {'ndcg':>8}"
    print(header)
    print("-" * len(header))
    aggregates = {}
    for stage in STAGES:
        agg = _aggregate(per_stage_rows[stage], is_unanswerable=False)
        aggregates[stage] = agg
        print(
            f"{stage:<14} {_fmt(agg['recall']):>8} {_fmt(agg['precision']):>10} "
            f"{_fmt(agg['mrr']):>8} {_fmt(agg['ndcg']):>8}"
        )
    return aggregates


async def run_eval(
    company_slug: str,
    user_email: str,
    dataset_path: Path,
    output_dir: Path,
    category_filter: str | None,
    limit: int | None,
) -> None:
    company = await _load_company(company_slug)
    user, role = await _load_user_and_role(user_email, company.id)

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    questions = dataset["questions"]
    if category_filter:
        questions = [q for q in questions if q["category"] == category_filter]
    if limit:
        questions = questions[:limit]

    if not questions:
        raise SystemExit("No questions to run (check --category / --limit).")

    print(f"Company: {company.name} ({company.slug}), schema={company.schema_name}")
    print(f"User: {user.email} (role={role})")
    print(f"Dataset: {dataset_path} — {len(questions)} question(s) selected")

    per_question_records: list[dict] = []
    missing_filenames: set[str] = set()

    async with _tenant_session(company.schema_name) as db:
        filename_map = await _load_filename_map(db, company.id)
        print(f"Documents found in tenant: {len(filename_map)} ({', '.join(filename_map) or 'none'})")

        for question in questions:
            is_unanswerable = question["category"] == "unanswerable"
            relevant_ids, missing = _relevant_ids_for(question, filename_map)
            missing_filenames.update(missing)

            debug_result = await run_retrieval_debug(
                db, company.id, user.id, question["question"]
            )

            stage_scores = {}
            stage_ranked_ids = {}
            for stage in STAGES:
                doc_id_sequence = [c["document_id"] for c in debug_result[stage]]
                ranked_doc_ids = dedupe_preserve_order(doc_id_sequence)
                stage_ranked_ids[stage] = ranked_doc_ids
                stage_scores[stage] = _score_stage(ranked_doc_ids, relevant_ids, is_unanswerable)

            per_question_records.append(
                {
                    "id": question["id"],
                    "category": question["category"],
                    "difficulty": question.get("difficulty"),
                    "question": question["question"],
                    "expected_source_document": question.get("expected_source_document"),
                    "relevant_document_ids": sorted(relevant_ids),
                    "accessible_document_count": debug_result["accessible_document_count"],
                    "stage_ranked_document_ids": stage_ranked_ids,
                    "stage_scores": stage_scores,
                }
            )

    if missing_filenames:
        print(
            "\nWARNING: these expected_source_document filenames were not found as "
            f"uploaded documents for this company (upload/re-check them first): "
            f"{sorted(missing_filenames)}"
        )

    by_category: dict[str, list[dict]] = defaultdict(list)
    for record in per_question_records:
        by_category[record["category"]].append(record)

    report_aggregates: dict[str, dict] = {}

    answerable_records = [r for r in per_question_records if r["category"] != "unanswerable"]
    if answerable_records:
        rows_by_stage = {
            stage: [r["stage_scores"][stage] for r in answerable_records] for stage in STAGES
        }
        report_aggregates["overall_answerable"] = _print_stage_table(
            "=== OVERALL (all answerable categories) ===", rows_by_stage, is_unanswerable=False
        )

    for category, records in sorted(by_category.items()):
        is_unanswerable = category == "unanswerable"
        rows_by_stage = {
            stage: [r["stage_scores"][stage] for r in records] for stage in STAGES
        }
        report_aggregates[category] = _print_stage_table(
            f"--- category: {category} (n={len(records)}) ---",
            rows_by_stage,
            is_unanswerable=is_unanswerable,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"{timestamp}__{company_slug}.json"
    output_path.write_text(
        json.dumps(
            {
                "run_at": timestamp,
                "company_slug": company_slug,
                "user_email": user_email,
                "dataset_path": str(dataset_path),
                "category_filter": category_filter,
                "question_count": len(per_question_records),
                "aggregates": report_aggregates,
                "missing_filenames": sorted(missing_filenames),
                "questions": per_question_records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved full results to {output_path}")
    print(
        "Compare this file against a previous run's to see what a pipeline change "
        "actually did — see build_docs/06-evaluation-guide.md §9.1."
    )


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

