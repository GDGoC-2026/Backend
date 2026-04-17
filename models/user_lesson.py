import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from Backend.db.base import Base


class UserLesson(Base):
    __tablename__ = "user_lessons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    pages: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    navigation: Mapped[dict] = mapped_column(JSON, nullable=False)

    source_documents: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    execution_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    quality_metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    workflow_issues: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    current_page_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    completed_page_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

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
    last_opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
