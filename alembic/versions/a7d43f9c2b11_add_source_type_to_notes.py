"""add source_type discriminator to notes

Revision ID: a7d43f9c2b11
Revises: c8a1f2479a12
Create Date: 2026-04-18 19:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7d43f9c2b11"
down_revision: Union[str, Sequence[str], None] = "c8a1f2479a12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "notes",
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="note"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("notes", "source_type")
