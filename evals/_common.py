"""Shared DB plumbing for the evals/ scripts. Not meant to be imported outside
this package — see evals/run.py (retrieval-only) and evals/run_generation.py
(generation-side).
"""

from contextlib import asynccontextmanager

from sqlalchemy import event, select
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession

from app.database.database import AsyncSessionLocal, TENANT_SCHEMA
from app.models.company import Company, CompanyMember
from app.models.documents import Document
from app.models.user import User


@asynccontextmanager
async def tenant_session(schema_name: str):
    """Same schema_translate_map pattern as app/core/tenant_db.py, without the
    FastAPI Depends(CurrentUser) plumbing these CLI scripts don't have.
    """
    async with AsyncSessionLocal() as session:
        schema_translate_map = {TENANT_SCHEMA: schema_name}

        @event.listens_for(session.sync_session, "after_begin")
        def _apply_schema_translate_map(
            sync_session: SyncSession, transaction, connection: Connection
        ) -> None:
            connection.execution_options(schema_translate_map=schema_translate_map)

        yield session


async def load_company(slug: str) -> Company:
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


async def load_user_and_role(email: str, company_id) -> tuple[User, str]:
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


async def load_filename_map(db: AsyncSession, company_id) -> dict[str, str]:
    result = await db.execute(
        select(Document.original_filename, Document.id).where(
            Document.company_id == company_id
        )
    )
    return {filename: str(doc_id) for filename, doc_id in result.all()}
