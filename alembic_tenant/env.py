"""Alembic environment for the TENANT migration chain.

Unlike alembic/env.py (which migrates the single `public` schema once), this
environment applies each revision to *every* tenant schema — one per company,
named in `company.schema_name`. Migration scripts are written once, against
the TENANT_SCHEMA sentinel ("tenant"), and this file swaps that sentinel for a
real schema name on each loop iteration via
`connection.execution_options(schema_translate_map=...)` — this works for
*executing* `upgrade`/`downgrade` because that's pure SQL compilation, which
schema_translate_map does affect.

`revision --autogenerate` is a different story and gets special-cased below
(see `_run_migrations_for_schema`'s `autogenerate` branch): SQLAlchemy's
`Inspector` reflection calls (which autogenerate's comparison logic depends on
to see what's *actually* in the database) take a schema name as a literal
string and do NOT consult schema_translate_map at all — confirmed directly by
calling `inspect(conn).get_table_names(schema="tenant")` against a schema that
demonstrably had those tables, and getting back `[]`. So autogenerate instead
reflects/compares against a "shadow" copy of the tenant metadata with the
*real* schema name baked in (via `Table.to_metadata(..., schema=real_name)`),
then rewrites the resulting operations' `.schema` back to the sentinel before
the migration file is written, via `process_revision_directives`, so the
output file stays portable across every tenant schema like every other
migration in this chain. See build_docs/06-schema-per-tenant-migration.md §7
for the full story of how this was found.

Each tenant schema tracks its own `alembic_version` row (via
`version_table_schema=schema_name`), so schemas can be at different revisions
mid-rollout (e.g. right after a new company signs up but before the next
`alembic -c alembic_tenant.ini upgrade head` run touches older ones).

Run with:
  alembic -c alembic_tenant.ini upgrade head
  alembic -c alembic_tenant.ini -x schema=tenant_xxx revision --autogenerate -m "..."
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import MetaData, pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import settings
from app.database.database import Base, TENANT_SCHEMA
# Importing app.models registers every model (including the public ones) on
# Base.metadata; include_object below filters back down to just the tenant
# tables so this chain never tries to create/alter company/users/etc.
from app.models import Document, DocumentPermission, Group, GroupMember  # noqa: F401


config = context.config
config.set_main_option(
    "sqlalchemy.url",
    settings.database_url,
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _tenant_tables():
    return [t for t in Base.metadata.tables.values() if t.schema == TENANT_SCHEMA]


def _shadow_metadata(real_schema_name: str) -> MetaData:
    """A copy of the tenant tables with the sentinel schema replaced by the
    real one, purely so Inspector-based reflection (autogenerate's
    comparison step) can actually find what's already in the database.

    Index names need a manual fix-up after the copy: SQLAlchemy's default
    naming convention bakes the table's *schema* into an auto-named index
    (`ix_tenant_documents_company_id` when schema="tenant"), and every index
    that actually exists in the database was named that way at the sentinel
    schema — `to_metadata()` regenerates the name using the shadow table's
    real schema instead (`ix_tenant_<hex>_documents_company_id`), which would
    make autogenerate see a spurious rename (drop + add) on every single
    index, every time. Column-set matching (each index here covers a distinct
    column) is what pairs an original index back up with its shadow copy.
    """
    shadow = MetaData()
    for table in _tenant_tables():
        shadow_table = table.to_metadata(shadow, schema=real_schema_name)
        original_by_columns = {
            tuple(c.name for c in index.columns): index.name
            for index in table.indexes
        }
        for shadow_index in shadow_table.indexes:
            key = tuple(c.name for c in shadow_index.columns)
            if key in original_by_columns:
                shadow_index.name = original_by_columns[key]
    return shadow


def _rewrite_ops_schema(ops_container, from_schema: str, to_schema: str) -> None:
    """Recursively rewrite `.schema` on every autogenerate-produced operation
    from the real schema name back to the TENANT_SCHEMA sentinel, so the
    written migration file matches every hand-written one in this chain."""
    for op in getattr(ops_container, "ops", []):
        if getattr(op, "schema", None) == from_schema:
            op.schema = to_schema
        _rewrite_ops_schema(op, from_schema, to_schema)


def _make_include_object(expected_schema: str):
    def include_object(object, name, type_, reflected, compare_to):
        if type_ == "table":
            return getattr(object, "schema", None) == expected_schema
        return True

    return include_object


def _target_schema_override() -> str | None:
    """`-x schema=tenant_xxx` targets exactly one schema (used right after a
    new company signs up, for autogenerate, or for a one-off manual fix)
    instead of looping over every row in company.schema_name."""
    return context.get_x_argument(as_dictionary=True).get("schema")


def _get_tenant_schemas_sync(connection: Connection) -> list[str]:
    rows = connection.execute(
        text("SELECT schema_name FROM company WHERE schema_name IS NOT NULL")
    )
    return [row[0] for row in rows]


def _run_migrations_for_schema(
    connection: Connection, schema_name: str, autogenerate: bool
) -> None:
    schema_scoped_connection = connection.execution_options(
        schema_translate_map={TENANT_SCHEMA: schema_name}
    )

    if autogenerate:
        metadata = _shadow_metadata(schema_name)
        include_object = _make_include_object(schema_name)

        def process_revision_directives(ctx, rev, directives) -> None:
            script = directives[0]
            _rewrite_ops_schema(script.upgrade_ops, schema_name, TENANT_SCHEMA)
            _rewrite_ops_schema(script.downgrade_ops, schema_name, TENANT_SCHEMA)
    else:
        metadata = target_metadata
        include_object = _make_include_object(TENANT_SCHEMA)
        process_revision_directives = None

    context.configure(
        connection=schema_scoped_connection,
        target_metadata=metadata,
        include_object=include_object,
        include_schemas=True,
        version_table="alembic_version",
        version_table_schema=schema_name,
        process_revision_directives=process_revision_directives,
    )
    with context.begin_transaction():
        context.run_migrations()


def _is_autogenerate() -> bool:
    cmd_opts = getattr(config, "cmd_opts", None)
    return bool(getattr(cmd_opts, "autogenerate", False))


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as listing_connection:
        override = _target_schema_override()
        if override:
            schemas = [override]
        else:
            schemas = await listing_connection.run_sync(_get_tenant_schemas_sync)

    autogenerate = _is_autogenerate()
    if autogenerate:
        # `alembic revision --autogenerate` diffs the models against one real
        # schema and writes ONE new migration file. Looping over every
        # tenant schema here (right for upgrade/downgrade) would be wrong for
        # this command — it would try to autogenerate the same diff once per
        # schema instead of writing a single revision.
        if not schemas:
            raise RuntimeError(
                "No tenant schema exists yet to autogenerate against. "
                "Create at least one company first, or pass an explicit "
                "one: alembic -c alembic_tenant.ini -x schema=<tenant_...> "
                "revision --autogenerate -m '...'"
            )
        schemas = schemas[:1]

    # Each schema gets migrated on its own fresh connection, opened and
    # closed inside this loop iteration, rather than one connection shared
    # across every schema. Found necessary by actually running this: sharing
    # one connection meant the listing SELECT above left it in an ambient
    # transaction, and every subsequent per-schema `context.begin_transaction()`
    # then failed to durably commit — `upgrade head` reported success for
    # every schema in its log output, but none of the DDL actually persisted
    # once the outer connection closed (an implicit rollback of whatever
    # transaction state was still open). See
    # build_docs/06-schema-per-tenant-migration.md §7.
    for schema_name in schemas:
        async with connectable.connect() as connection:
            await connection.run_sync(
                _run_migrations_for_schema, schema_name, autogenerate
            )
            await connection.commit()

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


def run_migrations_offline() -> None:
    raise RuntimeError(
        "Offline mode is not supported for the tenant migration chain — it "
        "needs a live connection to enumerate company.schema_name. Run "
        "'alembic -c alembic_tenant.ini upgrade head' against a real database."
    )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
