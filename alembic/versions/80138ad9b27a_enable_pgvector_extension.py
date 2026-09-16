"""enable pgvector extension

Revision ID: 80138ad9b27a
Revises: d4e9a1c6f582
Create Date: 2026-09-16 18:08:49.014920

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80138ad9b27a'
down_revision: Union[str, Sequence[str], None] = 'd4e9a1c6f582'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP EXTENSION IF EXISTS vector")
