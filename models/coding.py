import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from Backend.db.base import Base


class CodingProblem(Base):
    __tablename__ = "coding_problems"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    source_lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_lessons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    topic: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False, default="python")
    language_id: Mapped[int] = mapped_column(Integer, nullable=False, default=71)

    starter_code: Mapped[str] = mapped_column(Text, nullable=False)
    solution_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_cases: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    hints: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    include_in_lesson: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CodingAttempt(Base):
    __tablename__ = "coding_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    coding_problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("coding_problems.id", ondelete="CASCADE"),
        index=True,
    )

    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # run | submit
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    language_id: Mapped[int] = mapped_column(Integer, nullable=False)

    overall_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    result_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    raw_result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
