"""Provisions a brand-new company's Postgres schema.

Called once, synchronously, inside the same transaction that inserts a new
`company` row (see app/services/auth.py::AuthService.signup_company). Because
`CREATE SCHEMA` / `CREATE TABLE` are transactional DDL in Postgres, running
this on the same AsyncSession as the company/user/company_member inserts means
the whole signup — identity rows *and* the tenant schema — commits or rolls
back together. There is no window where a `company` row exists without its
schema, or vice versa.

Every DDL statement here is compiled to a literal string with the real schema
name already baked in (`render_schema_translate=True`), rather than relying on
`schema_translate_map` set as a connection execution_option. That's a
deliberate choice, not a style preference: `AsyncSession.connection(
execution_options=...)` only takes effect if the session's connection hasn't
been used yet in the current transaction — by the time signup_company() calls
this, `self.db` has already run the domain-uniqueness SELECT and the
user/company INSERTs, so the connection is already established and
SQLAlchemy silently ignores execution_options passed after that point (it
emits `SAWarning: Connection is already established for the given bind;
execution_options ignored` — found by actually running this against a real
database while building it; see build_docs/06-schema-per-tenant-migration.md
§7 for how). Compiling the schema translation into the SQL text sidesteps the
connection-state question entirely.

See build_docs/06-schema-per-tenant-migration.md for the full design writeup,
including why this hand-builds `CREATE TABLE`/`CREATE INDEX` (rather than
running a live Alembic upgrade) for the initial tables, and then hand-stamps
`alembic_version` so the very next `alembic -c alembic_tenant.ini upgrade
head` (looping over every tenant schema, see alembic_tenant/env.py) treats
this schema as already caught up.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateIndex, CreateTable

from app.database.database import Base, TENANT_SCHEMA

TENANT_TABLES = [
    table for table in Base.metadata.tables.values() if table.schema == TENANT_SCHEMA
]

# FK-dependency order (documents/groups before document_permissions/group_members,
# which reference them) — Base.metadata.sorted_tables topologically sorts every
# table by its FK graph; filtering it down preserves that order for just the
# tenant subset.
_ORDERED_TENANT_TABLES = [t for t in Base.metadata.sorted_tables if t in TENANT_TABLES]

_DIALECT = postgresql.dialect()

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TENANT_ALEMBIC_INI = _REPO_ROOT / "alembic_tenant.ini"


def _compile(ddl_element, schema_name: str) -> str:
    return str(
        ddl_element.compile(
            dialect=_DIALECT,
            schema_translate_map={TENANT_SCHEMA: schema_name},
            render_schema_translate=True,
        )
    )


def _tenant_head_revision() -> str:
    cfg = Config(str(_TENANT_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_REPO_ROOT / "alembic_tenant"))
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    if head is None:
        raise RuntimeError(
            "alembic_tenant has no revisions yet — create the baseline tenant "
            "migration before provisioning any tenant schema."
        )
    return head


async def provision_tenant_schema(db: AsyncSession, schema_name: str) -> None:
    """Create `schema_name` and lay down every tenant-scoped table inside it.

    `schema_name` must already be a trusted, server-generated value (e.g.
    `f"tenant_{company_id.hex}"`) — it is interpolated directly into DDL below,
    so never pass client-supplied input here.
    """
    await db.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

    for table in _ORDERED_TENANT_TABLES:
        await db.execute(
            text(_compile(CreateTable(table, if_not_exists=True), schema_name))
        )
        for index in table.indexes:
            await db.execute(
                text(_compile(CreateIndex(index, if_not_exists=True), schema_name))
            )

    head = _tenant_head_revision()
    await db.execute(
        text(
            f'CREATE TABLE IF NOT EXISTS "{schema_name}".alembic_version '
            f"(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
        )
    )
    await db.execute(
        text(
            f'INSERT INTO "{schema_name}".alembic_version (version_num) '
            f"VALUES (:head) ON CONFLICT DO NOTHING"
        ),
        {"head": head},
    )
