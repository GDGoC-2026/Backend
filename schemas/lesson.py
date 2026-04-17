from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


LessonPageType = Literal[
    "overview",
    "theory",
    "flashcards",
    "quiz",
    "coding",
    "mindmap",
    "resources",
]


class LessonSourceDocument(BaseModel):
    file_name: str
    file_type: str
    extracted_characters: int = Field(..., ge=0)
    excerpt: str | None = None


class LessonPage(BaseModel):
    page_id: str
    order: int = Field(..., ge=1)
    page_type: LessonPageType
    title: str
    description: str | None = None
    estimated_time_minutes: int | None = Field(default=None, ge=0)
    data: dict[str, Any] = Field(default_factory=dict)


class LessonNavigation(BaseModel):
    total_pages: int = Field(..., ge=1)
    page_order: list[str]
    default_page_id: str


class LessonGenerationResponse(BaseModel):
    success: bool
    lesson_id: str
    title: str
    topic: str
    prompt: str
    pages: list[LessonPage]
    navigation: LessonNavigation
    source_documents: list[LessonSourceDocument] = Field(default_factory=list)
    execution_summary: dict[str, Any] = Field(default_factory=dict)
    quality_metrics: dict[str, Any] = Field(default_factory=dict)
    workflow_issues: list[str] = Field(default_factory=list)


class LessonProgressSnapshot(BaseModel):
    current_page_id: str | None = None
    completed_page_ids: list[str] = Field(default_factory=list)
    total_pages: int = Field(..., ge=1)
    progress_percent: float = Field(..., ge=0.0, le=100.0)


class LessonSaveRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    topic: str = Field(..., min_length=1, max_length=255)
    prompt: str = Field(..., min_length=1)
    pages: list[LessonPage] = Field(..., min_length=1)
    navigation: LessonNavigation
    source_documents: list[LessonSourceDocument] = Field(default_factory=list)
    execution_summary: dict[str, Any] = Field(default_factory=dict)
    quality_metrics: dict[str, Any] = Field(default_factory=dict)
    workflow_issues: list[str] = Field(default_factory=list)
    current_page_id: str | None = None
    completed_page_ids: list[str] = Field(default_factory=list)


class LessonProgressUpdateRequest(BaseModel):
    current_page_id: str | None = None
    completed_page_ids: list[str] | None = None


class SavedLessonSummary(BaseModel):
    id: UUID
    title: str
    topic: str
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime
    progress: LessonProgressSnapshot


class SavedLessonDetail(SavedLessonSummary):
    prompt: str
    pages: list[LessonPage]
    navigation: LessonNavigation
    source_documents: list[LessonSourceDocument] = Field(default_factory=list)
    execution_summary: dict[str, Any] = Field(default_factory=dict)
    quality_metrics: dict[str, Any] = Field(default_factory=dict)
    workflow_issues: list[str] = Field(default_factory=list)
