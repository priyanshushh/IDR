"""One-time backfill: provision a tenant schema for every pre-existing company
and copy its rows out of the old `public.documents` / `document_permissions` /
`groups` / `group_members` tables.

Run once, after the main Alembic chain's `b7f21c9a4d3e_add_company_schema_name`
migration has added the (nullable) `company.schema_name` column, and before
`alembic -c alembic_tenant.ini upgrade head` is expected to find any schemas —
this script is what actually creates them for companies that existed before
schema-per-tenant.

Usage:
    python -m scripts.backfill_tenant_schemas
    python -m scripts.backfill_tenant_schemas --verify-only

Safe to re-run: schema/table creation is idempotent (CREATE ... IF NOT EXISTS
/ checkfirst=True) and every INSERT...SELECT below is scoped with
`ON CONFLICT (id) DO NOTHING`.

This script does NOT drop the old public.documents/document_permissions/
groups/group_members tables or rows — see build_docs/06-schema-per-tenant-
migration.md for that step, done by hand after you've verified row counts.
"""

import argparse
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import AsyncSessionLocal
from app.database.tenant_provisioning import provision_tenant_schema

# (label, statement) — order matters: groups before group_members/
# document_permissions (FKs), documents before document_permissions (FK).
_COPY_STATEMENTS = [
    (
        "groups",
        """
        INSERT INTO "{schema}".groups
            (id, company_id, name, is_default, created_by, updated_by, created_at, updated_at)
        SELECT id, company_id, name, is_default, created_by, updated_by, created_at, updated_at
        FROM public.groups
        WHERE company_id = :company_id
        ON CONFLICT (id) DO NOTHING
        """,
    ),
    (
        "group_members",
        """
        INSERT INTO "{schema}".group_members (id, group_id, user_id)
        SELECT gm.id, gm.group_id, gm.user_id
        FROM public.group_members gm
        JOIN public.groups g ON g.id = gm.group_id
        WHERE g.company_id = :company_id
        ON CONFLICT (id) DO NOTHING
        """,
    ),
    (
        "documents",
        """
        INSERT INTO "{schema}".documents
            (id, company_id, uploaded_by, name, original_filename, source, document_type,
             category, storage_key, mime_type, size_bytes, visibility, created_at, is_active)
        SELECT id, company_id, uploaded_by, name, original_filename, source, document_type,
               category, storage_key, mime_type, size_bytes, visibility, created_at, is_active
        FROM public.documents
        WHERE company_id = :company_id
        ON CONFLICT (id) DO NOTHING
        """,
    ),
    (
        "document_permissions",
        """
        INSERT INTO "{schema}".document_permissions
            (id, document_id, group_id, user_id, company_id, created_at)
        SELECT id, document_id, group_id, user_id, company_id, created_at
        FROM public.document_permissions
        WHERE company_id = :company_id
        ON CONFLICT (id) DO NOTHING
        """,
    ),
]


async def _companies_missing_schema(session: AsyncSession):
    result = await session.execute(
        text("SELECT id, name FROM company WHERE schema_name IS NULL ORDER BY created_at")
    )
    return result.all()


async def backfill(verify_only: bool) -> None:
    async with AsyncSessionLocal() as session:
        companies = await _companies_missing_schema(session)

        if not companies:
            print("Every company already has a schema_name. Nothing to do.")
            return

        print(f"{len(companies)} company row(s) missing schema_name:")
        for company_id, name in companies:
            print(f"  - {name} ({company_id})")

        if verify_only:
            return

        for company_id, name in companies:
            schema_name = f"tenant_{company_id.hex}"
            print(f"Provisioning {schema_name!r} for {name!r}...")

            await provision_tenant_schema(session, schema_name)

            for table_name, statement in _COPY_STATEMENTS:
                result = await session.execute(
                    text(statement.format(schema=schema_name)),
                    {"company_id": company_id},
                )
                print(f"    copied {result.rowcount} row(s) into {schema_name}.{table_name}")

            await session.execute(
                text("UPDATE company SET schema_name = :schema_name WHERE id = :company_id"),
                {"schema_name": schema_name, "company_id": company_id},
            )
            await session.commit()
            print(f"  done: company.schema_name = {schema_name!r}")

        print(
            "\nBackfill complete. Next steps (see "
            "build_docs/06-schema-per-tenant-migration.md):\n"
            "  1. Spot-check row counts between public.* and each tenant_*.* table.\n"
            "  2. Run `alembic upgrade head` (main chain) to enforce schema_name NOT NULL.\n"
            "  3. Once confident, manually drop the old public.documents / "
            "document_permissions / groups / group_members tables."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="List companies missing a schema_name without provisioning anything.",
    )
    args = parser.parse_args()
    asyncio.run(backfill(verify_only=args.verify_only))


if __name__ == "__main__":
    main()
