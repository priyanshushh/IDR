"""cascade document_chunks on document delete

Revision ID: 31ed543d3307
Revises: 4f45fd6ef4f2
Create Date: 2026-09-19 17:25:03.371391

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31ed543d3307'
down_revision: Union[str, Sequence[str], None] = '4f45fd6ef4f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every op.create_table/op.add_column/etc. in this migration chain must pass
# schema=TENANT_SCHEMA — env.py's schema_translate_map turns that sentinel into
# the real "tenant_<id>" schema once per company as this migration is applied.
TENANT_SCHEMA = "tenant"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        "document_chunks_document_id_fkey",
        "document_chunks",
        schema=TENANT_SCHEMA,
        type_="foreignkey",
    )
    op.create_foreign_key(
        "document_chunks_document_id_fkey",
        "document_chunks",
        "documents",
        ["document_id"],
        ["id"],
        source_schema=TENANT_SCHEMA,
        referent_schema=TENANT_SCHEMA,
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "document_chunks_document_id_fkey",
        "document_chunks",
        schema=TENANT_SCHEMA,
        type_="foreignkey",
    )
    op.create_foreign_key(
        "document_chunks_document_id_fkey",
        "document_chunks",
        "documents",
        ["document_id"],
        ["id"],
        source_schema=TENANT_SCHEMA,
        referent_schema=TENANT_SCHEMA,
    )
