from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


DifficultyLevel = Literal["beginner", "intermediate", "advanced"]
LearningStyle = Literal["visual", "auditory", "kinesthetic", "reading/writing"]
LearningPace = Literal["slow", "normal", "fast"]
QuizQuestionType = Literal["multiple_choice", "fill_blank", "true_false"]


class QuizQuestion(BaseModel):
    id: int = Field(..., ge=1)
    type: QuizQuestionType
    question: str
    subtopic: str | None = None
    options: list[str] | None = None
    correct_answer: int | str | bool | None = None
    correct_answers: list[str] | None = None
    explanation: str | None = None
    difficulty: str | None = None
    learning_value: str | None = None


class QuizGenerationRequest(BaseModel):
    topic: str = Field(..., min_length=2, description="Primary quiz topic")
    subject: str | None = Field(None, description="Subject/domain. Defaults to topic when omitted")
    subtopics: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)

    student_name: str | None = Field(None, description="Optional learner display name")
    current_level: DifficultyLevel = "intermediate"
    learning_style: LearningStyle = "visual"
    learning_pace: LearningPace = "normal"
    knowledge_gaps: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)

    max_questions: int = Field(default=10, ge=1, le=50)
    preferred_question_types: list[QuizQuestionType] = Field(
        default_factory=lambda: ["multiple_choice", "fill_blank", "true_false"]
    )
    daily_study_time_minutes: int = Field(default=30, ge=5, le=300)
    include_debug: bool = Field(default=False, description="Include workflow execution debug payload")


class QuizGenerationResponse(BaseModel):
    success: bool
    quiz_id: str
    topic: str
    quiz: dict[str, Any]
    questions: list[QuizQuestion]
    total_questions: int
    question_types: list[str]
    difficulty_distribution: dict[str, int]
    estimated_duration_minutes: int
    quality_score: float
    quality_passed: bool
    execution_summary: dict[str, Any]
    workflow_issues: list[str] = Field(default_factory=list)
    workflow_debug: dict[str, Any] | None = None


class QuizAnswerInput(BaseModel):
    question_id: int = Field(..., ge=1)
    answer: Any
    time_spent_seconds: int | None = Field(default=None, ge=0)


class QuizEvaluationRequest(BaseModel):
    questions: list[QuizQuestion] = Field(..., min_length=1)
    answers: list[QuizAnswerInput] = Field(default_factory=list)
    quiz_id: str | None = Field(default=None, description="Stable quiz identifier used for retry tracking")
    topic: str | None = Field(default=None, description="Optional topic override for analytics grouping")
    source_lesson_id: UUID | None = Field(default=None, description="Optional lesson identifier if quiz came from a saved lesson")
    passing_score: float = Field(default=70.0, ge=0, le=100)
    case_sensitive: bool = False


class QuestionEvaluationResult(BaseModel):
    question_id: int
    question_type: str
    is_correct: bool
    user_answer: Any = None
    expected_answer: Any = None
    explanation: str | None = None
    subtopic: str | None = None


class QuizEvaluationResponse(BaseModel):
    success: bool
    attempt_id: UUID | None = None
    quiz_id: str
    topic: str
    attempt_number: int = 1
    is_retry: bool = False
    previous_best_score: float | None = None
    total_questions: int
    answered_questions: int
    correct_answers: int
    score_percent: float
    passed: bool
    unanswered_question_ids: list[int]
    per_question_results: list[QuestionEvaluationResult]
    performance_by_type: dict[str, dict[str, float | int]]
    performance_by_subtopic: dict[str, dict[str, float | int]]
    recommendations: list[str] = Field(default_factory=list)
    gamification: dict[str, Any] | None = None


class QuizAttemptSummary(BaseModel):
    id: UUID
    quiz_id: str
    topic: str
    source_lesson_id: UUID | None = None
    attempt_number: int
    is_retry: bool
    total_questions: int
    answered_questions: int
    correct_answers: int
    score_percent: float
    passed: bool
    xp_awarded: int
    current_level_after: int | None = None
    created_at: datetime


class QuizAttemptDetail(QuizAttemptSummary):
    passing_score: float
    time_spent_seconds: int
    unanswered_question_ids: list[int] = Field(default_factory=list)
    submitted_answers: list[dict[str, Any]] = Field(default_factory=list)
    per_question_results: list[QuestionEvaluationResult] = Field(default_factory=list)
    performance_by_type: dict[str, dict[str, float | int]] = Field(default_factory=dict)
    performance_by_subtopic: dict[str, dict[str, float | int]] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


class QuizTopicAnalytics(BaseModel):
    topic: str
    attempts: int
    average_score: float
    best_score: float
    pass_rate: float
    retry_attempts: int


class QuizAnalyticsResponse(BaseModel):
    total_attempts: int
    unique_quizzes: int
    average_score: float
    best_score: float
    pass_rate: float
    retry_attempts: int
    retry_success_rate: float
    first_attempt_pass_rate: float
    improved_quiz_count: int
    total_xp_from_quizzes: int
    topic_analytics: list[QuizTopicAnalytics] = Field(default_factory=list)


class LessonQuizAnalyticsItem(BaseModel):
    quiz_id: str
    topic: str
    attempts: int
    average_score: float
    best_score: float
    pass_rate: float
    retry_attempts: int
    latest_attempt_at: datetime


class LessonQuizAnalyticsResponse(BaseModel):
    source_lesson_id: UUID
    total_attempts: int
    unique_quizzes: int
    average_score: float
    best_score: float
    pass_rate: float
    retry_attempts: int
    retry_success_rate: float
    first_attempt_pass_rate: float
    improved_quiz_count: int
    total_xp_from_quizzes: int
    quizzes: list[LessonQuizAnalyticsItem] = Field(default_factory=list)
