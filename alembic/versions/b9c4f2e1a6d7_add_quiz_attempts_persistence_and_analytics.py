"""add quiz attempts persistence and analytics

Revision ID: b9c4f2e1a6d7
Revises: f21c9e4a7b3d
Create Date: 2026-04-18 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9c4f2e1a6d7"
down_revision: Union[str, Sequence[str], None] = "f21c9e4a7b3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_lesson_id", sa.UUID(), nullable=True),
        sa.Column("quiz_id", sa.String(length=100), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("is_retry", sa.Boolean(), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("answered_questions", sa.Integer(), nullable=False),
        sa.Column("correct_answers", sa.Integer(), nullable=False),
        sa.Column("passing_score", sa.Float(), nullable=False),
        sa.Column("score_percent", sa.Float(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=False),
        sa.Column("unanswered_question_ids", sa.JSON(), nullable=False),
        sa.Column("submitted_answers", sa.JSON(), nullable=False),
        sa.Column("per_question_results", sa.JSON(), nullable=False),
        sa.Column("performance_by_type", sa.JSON(), nullable=False),
        sa.Column("performance_by_subtopic", sa.JSON(), nullable=False),
        sa.Column("recommendations", sa.JSON(), nullable=False),
        sa.Column("xp_awarded", sa.Integer(), nullable=False),
        sa.Column("current_level_after", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_lesson_id"], ["user_lessons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "quiz_id", "attempt_number", name="uq_quiz_attempt_user_quiz_attempt_number"),
    )
    op.create_index(op.f("ix_quiz_attempts_user_id"), "quiz_attempts", ["user_id"], unique=False)
    op.create_index(op.f("ix_quiz_attempts_source_lesson_id"), "quiz_attempts", ["source_lesson_id"], unique=False)
    op.create_index(op.f("ix_quiz_attempts_quiz_id"), "quiz_attempts", ["quiz_id"], unique=False)
    op.create_index(op.f("ix_quiz_attempts_topic"), "quiz_attempts", ["topic"], unique=False)
    op.create_index(op.f("ix_quiz_attempts_created_at"), "quiz_attempts", ["created_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_quiz_attempts_created_at"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_topic"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_quiz_id"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_source_lesson_id"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_user_id"), table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
