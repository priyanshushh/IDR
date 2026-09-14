"""company.schema_name NOT NULL

Run this only after every existing company has a schema_name — i.e. after
`python -m scripts.backfill_tenant_schemas` has been run against this
database and you've confirmed it reported zero remaining companies without a
schema. This migration refuses to run (raises, no partial changes) if it
still finds any NULL rows, rather than leaving the column half-migrated.

Revision ID: c8a34f0b6e21
Revises: b7f21c9a4d3e
Create Date: 2026-09-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8a34f0b6e21"
down_revision: Union[str, Sequence[str], None] = "b7f21c9a4d3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    remaining = connection.execute(
        sa.text("SELECT count(*) FROM company WHERE schema_name IS NULL")
    ).scalar_one()

    if remaining:
        raise RuntimeError(
            f"{remaining} company row(s) still have schema_name = NULL. "
            "Run `python -m scripts.backfill_tenant_schemas` first, then "
            "re-run this migration."
        )

    op.alter_column("company", "schema_name", existing_type=sa.String(length=63), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("company", "schema_name", existing_type=sa.String(length=63), nullable=True)
