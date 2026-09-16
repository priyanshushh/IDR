"""add document status

Revision ID: 4f45fd6ef4f2
Revises: b4e1155ac98e
Create Date: 2026-09-16 23:01:12.009146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f45fd6ef4f2'
down_revision: Union[str, Sequence[str], None] = 'b4e1155ac98e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every op.create_table/op.create_index/etc. in this migration chain must pass
# schema=TENANT_SCHEMA — env.py's schema_translate_map turns that sentinel into
# the real "tenant_<id>" schema once per company as this migration is applied,
# because those ops compile a real Table object and translate_map substitution
# happens at SQL-compile time.
#
# op.add_column / op.alter_column / op.drop_column are the exception: Alembic
# implements them with lightweight DDL classes that just string-format
# whatever `schema=` you pass, with NO compile-time translation — schema_name()
# below resolves the real schema at runtime instead. See
# build_docs/06-schema-per-tenant-migration.md §7 for the story on this.
TENANT_SCHEMA = "tenant"


def schema_name() -> str:
    translate_map = op.get_bind().get_execution_options().get(
        "schema_translate_map"
    ) or {}
    return translate_map.get(TENANT_SCHEMA, TENANT_SCHEMA)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'documents',
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        schema=schema_name(),
    )
    # Drop the server_default once existing rows are backfilled — the app
    # always supplies "pending" via the ORM default on new inserts, this is
    # only here so ADD COLUMN NOT NULL succeeds against schemas that already
    # have document rows.
    op.alter_column('documents', 'status', server_default=None, schema=schema_name())


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'status', schema=schema_name())
