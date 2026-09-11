"""updating group model

Revision ID: ac8f0d4b540d
Revises: 5c41caf657d6
Create Date: 2026-09-11 17:44:26.055740

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ac8f0d4b540d"
down_revision: Union[str, Sequence[str], None] = "5c41caf657d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Add the columns as nullable first.
    op.add_column(
        "groups",
        sa.Column("created_by", sa.UUID(), nullable=True),
    )

    op.add_column(
        "groups",
        sa.Column("updated_by", sa.UUID(), nullable=True),
    )

    op.add_column(
        "groups",
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.add_column(
        "groups",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # 2. Populate existing rows.
    #
    # Pick an existing user to be the creator/updater of
    # groups that existed before these columns were introduced.
    #
    # IMPORTANT:
    # Replace this logic with your actual business rule if
    # you know which user should own each existing group.
    op.execute(
        """
        UPDATE groups
        SET
            created_by = (SELECT id FROM users LIMIT 1),
            updated_by = (SELECT id FROM users LIMIT 1),
            created_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE created_by IS NULL
        """
    )

    # 3. Add foreign keys.
    op.create_foreign_key(
        "fk_groups_created_by_users",
        "groups",
        "users",
        ["created_by"],
        ["id"],
    )

    op.create_foreign_key(
        "fk_groups_updated_by_users",
        "groups",
        "users",
        ["updated_by"],
        ["id"],
    )

    # 4. Make the columns NOT NULL now that existing rows
    # have been populated.
    op.alter_column(
        "groups",
        "created_by",
        existing_type=sa.UUID(),
        nullable=False,
    )

    op.alter_column(
        "groups",
        "updated_by",
        existing_type=sa.UUID(),
        nullable=False,
    )

    op.alter_column(
        "groups",
        "created_at",
        existing_type=sa.DateTime(),
        nullable=False,
    )

    op.alter_column(
        "groups",
        "updated_at",
        existing_type=sa.DateTime(),
        nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        "fk_groups_updated_by_users",
        "groups",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_groups_created_by_users",
        "groups",
        type_="foreignkey",
    )

    op.drop_column("groups", "updated_at")
    op.drop_column("groups", "created_at")
    op.drop_column("groups", "updated_by")
    op.drop_column("groups", "created_by")
