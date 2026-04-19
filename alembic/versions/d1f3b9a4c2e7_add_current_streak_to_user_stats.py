"""add current_streak to user_stats

Revision ID: d1f3b9a4c2e7
Revises: a7d43f9c2b11
Create Date: 2026-04-19 11:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d1f3b9a4c2e7"
down_revision: Union[str, Sequence[str], None] = "a7d43f9c2b11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        ALTER TABLE user_stats
        ADD COLUMN IF NOT EXISTS current_streak INTEGER NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE user_stats
        ALTER COLUMN current_streak DROP DEFAULT
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        ALTER TABLE user_stats
        DROP COLUMN IF EXISTS current_streak
        """
    )
