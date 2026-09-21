"""update document chunks table to add metadata

Revision ID: 6c86c130d2dc
Revises: 31ed543d3307
Create Date: 2026-09-21 18:18:17.263609

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "6c86c130d2dc"
down_revision: Union[str, Sequence[str], None] = "31ed543d3307"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Sentinel schema.
#
# Your tenant env.py should use schema_translate_map to translate
# "tenant" into the actual tenant schema, e.g.
#
# tenant
#   ↓
# tenant_fbe796f4f300442d854f659264394981
#
TENANT_SCHEMA = "tenant"


def schema_name() -> str:
    # op.add_column/op.alter_column/op.drop_column build a lightweight DDL element
    # that string-formats whatever `schema=` you pass, with no compile-time
    # translation — unlike op.create_table/op.create_index, which compile a real
    # Table object and DO respect schema_translate_map. Resolve the real schema at
    # runtime instead of passing the TENANT_SCHEMA sentinel directly (see the same
    # fix in 4f45fd6ef4f2_add_document_status.py).
    translate_map = op.get_bind().get_execution_options().get(
        "schema_translate_map"
    ) or {}
    return translate_map.get(TENANT_SCHEMA, TENANT_SCHEMA)


def upgrade() -> None:
    """Add metadata column to document_chunks."""

    op.add_column(
        "document_chunks",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema=schema_name(),
    )

    # Existing rows are populated with {} by the server default.
    # Remove the default afterward so the application controls the value.
    op.alter_column(
        "document_chunks",
        "metadata",
        server_default=None,
        schema=schema_name(),
    )


def downgrade() -> None:
    """Remove metadata column from document_chunks."""

    op.drop_column(
        "document_chunks",
        "metadata",
        schema=schema_name(),
    )
