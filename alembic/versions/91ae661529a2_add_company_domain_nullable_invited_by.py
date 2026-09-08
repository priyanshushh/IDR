"""add company domain, nullable invited by

Revision ID: 91ae661529a2
Revises: 44b1410fe99d
Create Date: 2026-09-08 14:41:17.230077

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91ae661529a2'
down_revision: Union[str, Sequence[str], None] = '44b1410fe99d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Add domain as nullable first so existing rows don't violate NOT NULL.
    op.add_column(
        'company',
        sa.Column('domain', sa.String(length=255), nullable=True)
    )

    # Backfill existing companies with a unique temporary domain.
    # Replace this later with real domains if you have a way to derive them.
    op.execute("""
        UPDATE company
        SET domain = 'company-' || id::text || '.example.com'
        WHERE domain IS NULL
    """)

    # Now that all existing rows have a value, enforce NOT NULL.
    op.alter_column(
        'company',
        'domain',
        existing_type=sa.String(length=255),
        nullable=False,
    )

    # Domain must be unique.
    op.create_index(
        op.f('ix_company_domain'),
        'company',
        ['domain'],
        unique=True,
    )

    # invited_by is now nullable.
    op.alter_column(
        'company_members',
        'invited_by',
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.alter_column(
        'company_members',
        'invited_by',
        existing_type=sa.UUID(),
        nullable=False,
    )

    op.drop_index(
        op.f('ix_company_domain'),
        table_name='company',
    )

    op.drop_column('company', 'domain')