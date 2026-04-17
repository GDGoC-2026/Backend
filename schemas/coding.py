from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CodingTestCase(BaseModel):
    input: str = ""
    expected_output: str
    is_hidden: bool = False


class CodingProblemGenerateRequest(BaseModel):
    decision_mode: Literal["auto", "force", "skip"] = "auto"
    max_problems: int = Field(default=2, ge=1, le=5)


class CodingProblemSummary(BaseModel):
    id: UUID
    source_lesson_id: UUID | None = None
    topic: str
    title: str
    language: str
    language_id: int
    difficulty: str | None = None
    include_in_lesson: bool
    created_at: datetime
    updated_at: datetime


class CodingProblemDetail(CodingProblemSummary):
    instructions: str
    starter_code: str
    solution_code: str | None = None
    test_cases: list[CodingTestCase] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)


class CodingProblemsGenerationResponse(BaseModel):
    success: bool
    include_coding_exercises: bool
    reason: str
    generated_count: int
    problems: list[CodingProblemSummary] = Field(default_factory=list)


class CodeRunRequest(BaseModel):
    source_code: str = Field(..., min_length=1)
    language_id: int | None = Field(default=None, ge=1)
    stdin: str | None = None


class CodeRunResponse(BaseModel):
    success: bool
    attempt_id: UUID
    status: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    compile_output: str | None = None
    time: str | None = None
    memory: int | None = None
    raw_result: dict[str, Any] = Field(default_factory=dict)


class TestCaseResult(BaseModel):
    index: int
    input: str
    expected_output: str
    actual_output: str | None = None
    passed: bool
    status: str | None = None
    stderr: str | None = None
    compile_output: str | None = None
    time: str | None = None
    memory: int | None = None
    is_hidden: bool = False


class CodeSubmitRequest(BaseModel):
    source_code: str = Field(..., min_length=1)
    language_id: int | None = Field(default=None, ge=1)


class CodeSubmitResponse(BaseModel):
    success: bool
    attempt_id: UUID
    passed: bool
    total_tests: int
    passed_tests: int
    status: str | None = None
    results: list[TestCaseResult] = Field(default_factory=list)


class CodingAttemptSummary(BaseModel):
    id: UUID
    coding_problem_id: UUID
    mode: str
    language_id: int
    overall_status: str | None = None
    passed: bool
    total_tests: int
    passed_tests: int
    created_at: datetime


class CodingAttemptsResponse(BaseModel):
    attempts: list[CodingAttemptSummary] = Field(default_factory=list)
