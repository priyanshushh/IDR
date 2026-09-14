"""drop legacy public.documents/groups/group_members/document_permissions

These four tables were created by the original (pre-schema-per-tenant)
migrations in this same chain (`a5fb70b46f6e`, `ac8f0d4b540d`, ...) — that
history wasn't rewritten (rewriting applied migrations is its own risk), so a
fresh database still creates them in `public` as a side effect of running the
full chain, even though the real per-company data has lived in
`tenant_<company_id>` schemas since the schema-per-tenant migration (see
build_docs/06-schema-per-tenant-migration.md). This migration is what
actually removes that leftover.

Safety: this refuses to run (raises, no partial change) if it finds any rows
in these tables — that means there's pre-existing data that hasn't gone
through `python -m scripts.backfill_tenant_schemas` yet. Run that first (and
verify the copy), then re-run this migration.

Revision ID: d4e9a1c6f582
Revises: c8a34f0b6e21
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d4e9a1c6f582"
down_revision: Union[str, Sequence[str], None] = "c8a34f0b6e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ["document_permissions", "group_members", "documents", "groups"]


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()

    for table in _TABLES:
        remaining = connection.execute(
            sa.text(f"SELECT count(*) FROM public.{table}")
        ).scalar_one()
        if remaining:
            raise RuntimeError(
                f"public.{table} still has {remaining} row(s). Run "
                "`python -m scripts.backfill_tenant_schemas` first (it copies "
                "rows into each company's tenant_<id> schema), verify the "
                "counts match, then re-run this migration."
            )

    op.drop_table("document_permissions")
    op.drop_table("group_members")
    op.drop_table("documents")
    op.drop_table("groups")


def downgrade() -> None:
    """Downgrade schema — recreates the four tables exactly as they were at
    the top of the main chain (matching `a5fb70b46f6e`/`ac8f0d4b540d`), empty.
    This does not restore any data that a prior `upgrade()` refused to touch
    (nothing was ever dropped in that case) or that was dropped after a
    successful backfill (that data lives on in the tenant schemas either way).
    """
    op.create_table(
        "groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_groups_id"), "groups", ["id"], unique=True)

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("storage_key", sa.String(length=1000), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("visibility", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_id"), "documents", ["id"], unique=False)
    op.create_index(op.f("ix_documents_company_id"), "documents", ["company_id"], unique=False)

    op.create_table(
        "group_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_group_members_id"), "group_members", ["id"], unique=True)

    op.create_table(
        "document_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_permissions_id"), "document_permissions", ["id"], unique=False)
    op.create_index(op.f("ix_document_permissions_company_id"), "document_permissions", ["company_id"], unique=False)
    op.create_index(op.f("ix_document_permissions_document_id"), "document_permissions", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_permissions_group_id"), "document_permissions", ["group_id"], unique=False)
    op.create_index(op.f("ix_document_permissions_user_id"), "document_permissions", ["user_id"], unique=False)
