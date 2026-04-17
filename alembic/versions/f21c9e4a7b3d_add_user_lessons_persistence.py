"""add user lessons persistence

Revision ID: f21c9e4a7b3d
Revises: 6d05b521e2c4
Create Date: 2026-04-18 12:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f21c9e4a7b3d"
down_revision: Union[str, Sequence[str], None] = "6d05b521e2c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_lessons",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("pages", sa.JSON(), nullable=False),
        sa.Column("navigation", sa.JSON(), nullable=False),
        sa.Column("source_documents", sa.JSON(), nullable=False),
        sa.Column("execution_summary", sa.JSON(), nullable=False),
        sa.Column("quality_metrics", sa.JSON(), nullable=False),
        sa.Column("workflow_issues", sa.JSON(), nullable=False),
        sa.Column("current_page_id", sa.String(length=100), nullable=True),
        sa.Column("completed_page_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_lessons_user_id"), "user_lessons", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_lessons_updated_at"), "user_lessons", ["updated_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_user_lessons_updated_at"), table_name="user_lessons")
    op.drop_index(op.f("ix_user_lessons_user_id"), table_name="user_lessons")
    op.drop_table("user_lessons")
