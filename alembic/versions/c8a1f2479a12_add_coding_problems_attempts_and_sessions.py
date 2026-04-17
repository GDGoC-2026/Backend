"""add coding problems attempts and code session linkage

Revision ID: c8a1f2479a12
Revises: b9c4f2e1a6d7
Create Date: 2026-04-18 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8a1f2479a12"
down_revision: Union[str, Sequence[str], None] = "b9c4f2e1a6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "coding_problems",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_lesson_id", sa.UUID(), nullable=True),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=False),
        sa.Column("language_id", sa.Integer(), nullable=False),
        sa.Column("starter_code", sa.Text(), nullable=False),
        sa.Column("solution_code", sa.Text(), nullable=True),
        sa.Column("test_cases", sa.JSON(), nullable=False),
        sa.Column("hints", sa.JSON(), nullable=False),
        sa.Column("difficulty", sa.String(length=50), nullable=True),
        sa.Column("include_in_lesson", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_lesson_id"], ["user_lessons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coding_problems_user_id"), "coding_problems", ["user_id"], unique=False)
    op.create_index(op.f("ix_coding_problems_source_lesson_id"), "coding_problems", ["source_lesson_id"], unique=False)
    op.create_index(op.f("ix_coding_problems_topic"), "coding_problems", ["topic"], unique=False)

    op.create_table(
        "coding_attempts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("coding_problem_id", sa.UUID(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("language_id", sa.Integer(), nullable=False),
        sa.Column("overall_status", sa.String(length=100), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("total_tests", sa.Integer(), nullable=False),
        sa.Column("passed_tests", sa.Integer(), nullable=False),
        sa.Column("result_summary", sa.JSON(), nullable=False),
        sa.Column("raw_result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["coding_problem_id"], ["coding_problems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coding_attempts_user_id"), "coding_attempts", ["user_id"], unique=False)
    op.create_index(op.f("ix_coding_attempts_coding_problem_id"), "coding_attempts", ["coding_problem_id"], unique=False)
    op.create_index(op.f("ix_coding_attempts_created_at"), "coding_attempts", ["created_at"], unique=False)

    op.add_column("code_sessions", sa.Column("coding_problem_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_code_sessions_coding_problem_id"), "code_sessions", ["coding_problem_id"], unique=False)
    op.create_foreign_key(
        "fk_code_sessions_coding_problem_id_coding_problems",
        "code_sessions",
        "coding_problems",
        ["coding_problem_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_code_sessions_coding_problem_id_coding_problems", "code_sessions", type_="foreignkey")
    op.drop_index(op.f("ix_code_sessions_coding_problem_id"), table_name="code_sessions")
    op.drop_column("code_sessions", "coding_problem_id")

    op.drop_index(op.f("ix_coding_attempts_created_at"), table_name="coding_attempts")
    op.drop_index(op.f("ix_coding_attempts_coding_problem_id"), table_name="coding_attempts")
    op.drop_index(op.f("ix_coding_attempts_user_id"), table_name="coding_attempts")
    op.drop_table("coding_attempts")

    op.drop_index(op.f("ix_coding_problems_topic"), table_name="coding_problems")
    op.drop_index(op.f("ix_coding_problems_source_lesson_id"), table_name="coding_problems")
    op.drop_index(op.f("ix_coding_problems_user_id"), table_name="coding_problems")
    op.drop_table("coding_problems")
