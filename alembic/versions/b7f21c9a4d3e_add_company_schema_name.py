"""add company.schema_name

Nullable for now: existing companies (if any) don't have a tenant schema yet.
Run `python -m scripts.backfill_tenant_schemas` after this migration to
provision one per existing company and populate this column, then apply
`c8a34f0b6e21_company_schema_name_not_null` to lock it down. See
build_docs/06-schema-per-tenant-migration.md.

Revision ID: b7f21c9a4d3e
Revises: 4a7936cc87e3
Create Date: 2026-09-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7f21c9a4d3e"
down_revision: Union[str, Sequence[str], None] = "4a7936cc87e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "company",
        sa.Column("schema_name", sa.String(length=63), nullable=True),
    )
    op.create_index(
        op.f("ix_company_schema_name"), "company", ["schema_name"], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_company_schema_name"), table_name="company")
    op.drop_column("company", "schema_name")
