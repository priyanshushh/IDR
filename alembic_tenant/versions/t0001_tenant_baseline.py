"""tenant baseline: documents, document_permissions, groups, group_members

Mirrors the shape these four tables already have in `public` as of the main
chain's head (4a7936cc87e3) — this is the "day one" layout for every new
tenant schema, not a diff. See
build_docs/06-schema-per-tenant-migration.md for why these tables moved out
of `public` and why their cross-schema FKs (company_id -> company.id,
uploaded_by/created_by/updated_by/user_id -> users.id) were dropped in the
process (kept as plain columns, no constraint — see the model files for the
same note).

Revision ID: t0001_tenant_baseline
Revises:
Create Date: 2026-09-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "t0001_tenant_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_SCHEMA = "tenant"


def upgrade() -> None:
    """Upgrade schema."""
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
        sa.PrimaryKeyConstraint("id"),
        schema=TENANT_SCHEMA,
    )
    op.create_index(
        op.f("ix_tenant_groups_id"), "groups", ["id"], unique=True, schema=TENANT_SCHEMA
    )
    op.create_index(
        op.f("ix_tenant_groups_company_id"), "groups", ["company_id"], unique=False, schema=TENANT_SCHEMA
    )

    op.create_table(
        "group_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], [f"{TENANT_SCHEMA}.groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=TENANT_SCHEMA,
    )
    op.create_index(
        op.f("ix_tenant_group_members_id"), "group_members", ["id"], unique=True, schema=TENANT_SCHEMA
    )

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
        sa.PrimaryKeyConstraint("id"),
        schema=TENANT_SCHEMA,
    )
    op.create_index(
        op.f("ix_tenant_documents_id"), "documents", ["id"], unique=False, schema=TENANT_SCHEMA
    )
    op.create_index(
        op.f("ix_tenant_documents_company_id"), "documents", ["company_id"], unique=False, schema=TENANT_SCHEMA
    )

    op.create_table(
        "document_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], [f"{TENANT_SCHEMA}.documents.id"]),
        sa.ForeignKeyConstraint(["group_id"], [f"{TENANT_SCHEMA}.groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=TENANT_SCHEMA,
    )
    op.create_index(
        op.f("ix_tenant_document_permissions_id"), "document_permissions", ["id"], unique=False, schema=TENANT_SCHEMA
    )
    op.create_index(
        op.f("ix_tenant_document_permissions_document_id"), "document_permissions", ["document_id"], unique=False, schema=TENANT_SCHEMA
    )
    op.create_index(
        op.f("ix_tenant_document_permissions_group_id"), "document_permissions", ["group_id"], unique=False, schema=TENANT_SCHEMA
    )
    op.create_index(
        op.f("ix_tenant_document_permissions_user_id"), "document_permissions", ["user_id"], unique=False, schema=TENANT_SCHEMA
    )
    op.create_index(
        op.f("ix_tenant_document_permissions_company_id"), "document_permissions", ["company_id"], unique=False, schema=TENANT_SCHEMA
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("document_permissions", schema=TENANT_SCHEMA)
    op.drop_table("documents", schema=TENANT_SCHEMA)
    op.drop_table("group_members", schema=TENANT_SCHEMA)
    op.drop_table("groups", schema=TENANT_SCHEMA)
