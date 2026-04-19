"""restore missing revision bridge

Revision ID: a7d43f9c2b11
Revises: c8a1f2479a12
Create Date: 2026-04-19 22:35:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a7d43f9c2b11"
down_revision: Union[str, Sequence[str], None] = "c8a1f2479a12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Compatibility bridge for databases stamped with legacy revision a7d43f9c2b11.
    pass


def downgrade() -> None:
    pass
