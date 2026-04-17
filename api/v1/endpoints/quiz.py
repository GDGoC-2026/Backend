import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Backend.api.deps import get_current_user
from Backend.db.session import get_db
from Backend.models.learning import QuizAttempt
from Backend.models.user_lesson import UserLesson
from Backend.models.user import User
from Backend.schemas.quiz import (
    LessonQuizAnalyticsItem,
    LessonQuizAnalyticsResponse,
    QuizAnalyticsResponse,
    QuizAttemptDetail,
    QuizAttemptSummary,
    QuestionEvaluationResult,
    QuizTopicAnalytics,
    QuizAnswerInput,
    QuizEvaluationRequest,
    QuizEvaluationResponse,
    QuizGenerationRequest,
    QuizGenerationResponse,
    QuizQuestion,
)
from Backend.services.gamification import GamificationEngine
from Backend.services.workflows import ExerciseOrchestrator
from Backend.services.workflows.config import (
    ContentGenerationRequest,
    ContentLevel,
    ContentType,
    StudentProfile,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _normalize_distribution(raw_distribution: dict[Any, Any]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key, value in raw_distribution.items():
        normalized[str(_enum_value(key))] = int(value)
    return normalized


def _normalize_question_payload(question: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(question)
    normalized["difficulty"] = str(_enum_value(normalized.get("difficulty"))) if normalized.get("difficulty") is not None else None

    if normalized.get("type") == "fill_blank" and normalized.get("correct_answers") is None:
        if normalized.get("correct_answer") is not None:
            normalized["correct_answers"] = [str(normalized["correct_answer"])]

    return normalized


def _create_workflow_request(
    payload: QuizGenerationRequest,
    current_user: User,
) -> ContentGenerationRequest:
    subtopics = payload.subtopics or [payload.topic]
    objectives = payload.learning_objectives or [f"Understand core concepts of {payload.topic}"]

    student_profile = StudentProfile(
        student_id=str(current_user.id),
        name=payload.student_name or current_user.full_name or current_user.email,
        subject=payload.subject or payload.topic,
        current_level=ContentLevel(payload.current_level),
        learning_style=payload.learning_style,
        knowledge_gaps=payload.knowledge_gaps,
        strengths=payload.strengths,
        learning_pace=payload.learning_pace,
        preferred_content_types=[ContentType.QUIZ],
        daily_study_time_minutes=payload.daily_study_time_minutes,
    )

    return ContentGenerationRequest(
        student_profile=student_profile,
        topic=payload.topic,
        subtopics=subtopics,
        learning_objectives=objectives,
        content_types=[ContentType.QUIZ],
        max_items=payload.max_questions,
        quiz_question_types=list(payload.preferred_question_types),
    )


def _extract_quiz_data(workflow_data: dict[str, Any]) -> dict[str, Any] | None:
    workflow_log = workflow_data.get("workflow_log", [])

    for entry in workflow_log:
        if entry.get("agent") == "QuizCreatorAgent" and entry.get("success"):
            return entry.get("data")

    return None


def _normalize_text(value: Any, case_sensitive: bool) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if case_sensitive else text.lower()


def _parse_option_index(answer: Any, options: list[str] | None) -> int | None:
    if answer is None or isinstance(answer, bool):
        return None

    if isinstance(answer, int):
        if options and 1 <= answer <= len(options):
            return answer - 1
        return answer

    if isinstance(answer, str):
        stripped = answer.strip()
        if stripped.isdigit():
            numeric = int(stripped)
            if options and 1 <= numeric <= len(options):
                return numeric - 1
            return numeric

        if options and len(stripped) == 1 and stripped.upper() in {"A", "B", "C", "D", "E", "F"}:
            letter_index = ord(stripped.upper()) - ord("A")
            if 0 <= letter_index < len(options):
                return letter_index

        if options:
            for index, option in enumerate(options):
                if stripped.casefold() == option.casefold():
                    return index

    return None


def _parse_boolean_answer(answer: Any) -> bool | None:
    if answer is None:
        return None

    if isinstance(answer, bool):
        return answer

    if isinstance(answer, (int, float)) and answer in {0, 1}:
        return bool(answer)

    if isinstance(answer, str):
        normalized = answer.strip().lower()
        if normalized in {"true", "t", "1", "yes", "y"}:
            return True
        if normalized in {"false", "f", "0", "no", "n"}:
            return False

    return None


def _grade_single_question(
    question: QuizQuestion,
    user_answer: Any,
    case_sensitive: bool,
) -> tuple[bool, Any]:
    if question.type == "multiple_choice":
        options = question.options or []
        expected_index = _parse_option_index(question.correct_answer, options)
        if isinstance(question.correct_answer, int):
            expected_index = question.correct_answer

        user_index = _parse_option_index(user_answer, options)
        is_correct = (
            expected_index is not None
            and user_index is not None
            and expected_index == user_index
        )

        if expected_index is not None and 0 <= expected_index < len(options):
            expected_answer = options[expected_index]
        else:
            expected_answer = question.correct_answer

        return is_correct, expected_answer

    if question.type == "true_false":
        expected_bool = _parse_boolean_answer(question.correct_answer)
        user_bool = _parse_boolean_answer(user_answer)
        is_correct = (
            expected_bool is not None
            and user_bool is not None
            and expected_bool == user_bool
        )
        return is_correct, expected_bool

    if question.type == "fill_blank":
        expected_answers = question.correct_answers or []
        if not expected_answers and question.correct_answer is not None:
            expected_answers = [str(question.correct_answer)]

        normalized_user = _normalize_text(user_answer, case_sensitive)
        normalized_expected = {
            _normalize_text(answer, case_sensitive)
            for answer in expected_answers
        }

        is_correct = (
            normalized_user is not None
            and normalized_user in normalized_expected
        )
        return is_correct, expected_answers

    expected_answer = question.correct_answer
    return (
        _normalize_text(user_answer, case_sensitive)
        == _normalize_text(expected_answer, case_sensitive),
        expected_answer,
    )


def _calculate_accuracy(total: int, correct: int) -> float:
    if total <= 0:
        return 0.0
    return round((correct / total) * 100, 2)


def _resolve_topic(payload_topic: str | None, questions: list[QuizQuestion]) -> str:
    if payload_topic and payload_topic.strip():
        return payload_topic.strip()

    for question in questions:
        if question.subtopic and question.subtopic.strip():
            return question.subtopic.strip()

    return "General Quiz"


def _build_submitted_answers_payload(answers: list[QuizAnswerInput]) -> list[dict[str, Any]]:
    return [
        {
            "question_id": answer.question_id,
            "answer": answer.answer,
            "time_spent_seconds": answer.time_spent_seconds,
        }
        for answer in answers
    ]


def _calculate_quiz_xp(score_percent: float, passed: bool, is_retry: bool) -> int:
    base_xp = 8
    score_bonus = int(max(0, min(100.0, score_percent)) // 10)
    pass_bonus = 12 if passed else 0
    retry_penalty = 2 if is_retry else 0

    return max(4, base_xp + score_bonus + pass_bonus - retry_penalty)


def _serialize_attempt_summary(attempt: QuizAttempt) -> QuizAttemptSummary:
    return QuizAttemptSummary(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        topic=attempt.topic,
        source_lesson_id=attempt.source_lesson_id,
        attempt_number=attempt.attempt_number,
        is_retry=attempt.is_retry,
        total_questions=attempt.total_questions,
        answered_questions=attempt.answered_questions,
        correct_answers=attempt.correct_answers,
        score_percent=attempt.score_percent,
        passed=attempt.passed,
        xp_awarded=attempt.xp_awarded,
        current_level_after=attempt.current_level_after,
        created_at=attempt.created_at,
    )


def _serialize_attempt_detail(attempt: QuizAttempt) -> QuizAttemptDetail:
    per_question_results = [
        QuestionEvaluationResult.model_validate(item)
        for item in (attempt.per_question_results or [])
    ]

    summary = _serialize_attempt_summary(attempt)
    return QuizAttemptDetail(
        **summary.model_dump(),
        passing_score=attempt.passing_score,
        time_spent_seconds=attempt.time_spent_seconds,
        unanswered_question_ids=attempt.unanswered_question_ids or [],
        submitted_answers=attempt.submitted_answers or [],
        per_question_results=per_question_results,
        performance_by_type=attempt.performance_by_type or {},
        performance_by_subtopic=attempt.performance_by_subtopic or {},
        recommendations=attempt.recommendations or [],
    )


def _build_recommendations(
    passed: bool,
    unanswered_question_ids: list[int],
    performance_by_subtopic: dict[str, dict[str, float | int]],
    performance_by_type: dict[str, dict[str, float | int]],
) -> list[str]:
    recommendations: list[str] = []

    if unanswered_question_ids:
        recommendations.append(
            "Some questions were left unanswered. Try answering every question to improve your score consistency."
        )

    weak_subtopics = [
        subtopic
        for subtopic, stats in performance_by_subtopic.items()
        if stats["total"] > 0 and float(stats["accuracy"]) < 60.0
    ]
    if weak_subtopics:
        recommendations.append(
            "Review these subtopics: " + ", ".join(sorted(weak_subtopics))
        )

    weak_question_types = [
        question_type
        for question_type, stats in performance_by_type.items()
        if stats["total"] > 0 and float(stats["accuracy"]) < 60.0
    ]
    if weak_question_types:
        recommendations.append(
            "Practice more with these question formats: "
            + ", ".join(sorted(weak_question_types))
        )

    if not passed:
        recommendations.append(
            "Read each explanation for incorrect answers and retry with focused revision."
        )

    if not recommendations:
        recommendations.append(
            "Strong performance across all sections. Keep practicing to retain mastery."
        )

    return recommendations


@router.post("/generate", response_model=QuizGenerationResponse)
async def generate_quiz(
    payload: QuizGenerationRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate a personalized quiz by routing the request through ExerciseOrchestrator."""
    try:
        workflow_request = _create_workflow_request(payload, current_user)

        orchestrator = ExerciseOrchestrator()
        orchestrator_result = await orchestrator.run({"request": workflow_request})

        if not orchestrator_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=orchestrator_result.get("error", "Quiz generation failed"),
            )

        workflow_data = orchestrator_result.get("data", {})
        quiz_data = _extract_quiz_data(workflow_data)

        if not quiz_data:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Quiz agent did not return quiz content",
            )

        normalized_questions = [
            QuizQuestion(**_normalize_question_payload(question))
            for question in quiz_data.get("questions", [])
        ]

        if not normalized_questions:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No quiz questions were generated",
            )

        quality_metrics = workflow_data.get("quality_metrics", {})
        quality_score = float(quiz_data.get("quality_score", 0.0))

        response = QuizGenerationResponse(
            success=True,
            quiz_id=str(uuid4()),
            topic=payload.topic,
            quiz=quiz_data.get("quiz", {}),
            questions=normalized_questions,
            total_questions=int(quiz_data.get("total_questions", len(normalized_questions))),
            question_types=[str(item) for item in quiz_data.get("question_types", [])],
            difficulty_distribution=_normalize_distribution(quiz_data.get("difficulty_distribution", {})),
            estimated_duration_minutes=int(quiz_data.get("estimated_duration_minutes", len(normalized_questions) * 2)),
            quality_score=quality_score,
            quality_passed=bool(quality_metrics.get("passed_qa", True)) and quality_score >= 0.7,
            execution_summary=workflow_data.get("execution_summary", {}),
            workflow_issues=quality_metrics.get("quality_issues", []),
            workflow_debug=(
                {
                    "workflow_log": workflow_data.get("workflow_log", []),
                    "quality_metrics": quality_metrics,
                }
                if payload.include_debug
                else None
            ),
        )

        return response

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error while generating quiz")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/evaluate", response_model=QuizEvaluationResponse)
async def evaluate_quiz(
    payload: QuizEvaluationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Evaluate submitted quiz answers and return detailed scoring diagnostics."""
    resolved_quiz_id = payload.quiz_id or str(uuid4())
    resolved_topic = _resolve_topic(payload.topic, payload.questions)

    answers_by_question_id = {
        answer.question_id: answer
        for answer in payload.answers
    }

    per_question_results: list[QuestionEvaluationResult] = []
    unanswered_question_ids: list[int] = []

    by_type_tracker: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "correct": 0}
    )
    by_subtopic_tracker: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "correct": 0}
    )

    correct_answers = 0

    for question in payload.questions:
        answer_payload: QuizAnswerInput | None = answers_by_question_id.get(question.id)
        user_answer = answer_payload.answer if answer_payload else None

        question_type = question.type
        subtopic = question.subtopic or "General"

        by_type_tracker[question_type]["total"] += 1
        by_subtopic_tracker[subtopic]["total"] += 1

        if answer_payload is None:
            unanswered_question_ids.append(question.id)
            per_question_results.append(
                QuestionEvaluationResult(
                    question_id=question.id,
                    question_type=question_type,
                    is_correct=False,
                    user_answer=None,
                    expected_answer=question.correct_answers or question.correct_answer,
                    explanation=question.explanation,
                    subtopic=subtopic,
                )
            )
            continue

        is_correct, expected_answer = _grade_single_question(
            question=question,
            user_answer=user_answer,
            case_sensitive=payload.case_sensitive,
        )

        if is_correct:
            correct_answers += 1
            by_type_tracker[question_type]["correct"] += 1
            by_subtopic_tracker[subtopic]["correct"] += 1

        per_question_results.append(
            QuestionEvaluationResult(
                question_id=question.id,
                question_type=question_type,
                is_correct=is_correct,
                user_answer=user_answer,
                expected_answer=expected_answer,
                explanation=question.explanation,
                subtopic=subtopic,
            )
        )

    total_questions = len(payload.questions)
    answered_questions = total_questions - len(unanswered_question_ids)
    score_percent = _calculate_accuracy(total_questions, correct_answers)
    passed = score_percent >= payload.passing_score

    attempts_aggregate_result = await db.execute(
        select(
            func.count(QuizAttempt.id),
            func.max(QuizAttempt.score_percent),
        ).where(
            QuizAttempt.user_id == current_user.id,
            QuizAttempt.quiz_id == resolved_quiz_id,
        )
    )
    attempts_count, previous_best_score_raw = attempts_aggregate_result.one()

    attempt_number = int(attempts_count or 0) + 1
    is_retry = attempt_number > 1
    previous_best_score = (
        round(float(previous_best_score_raw), 2)
        if previous_best_score_raw is not None
        else None
    )

    performance_by_type = {
        question_type: {
            "total": stats["total"],
            "correct": stats["correct"],
            "accuracy": _calculate_accuracy(stats["total"], stats["correct"]),
        }
        for question_type, stats in by_type_tracker.items()
    }

    performance_by_subtopic = {
        subtopic: {
            "total": stats["total"],
            "correct": stats["correct"],
            "accuracy": _calculate_accuracy(stats["total"], stats["correct"]),
        }
        for subtopic, stats in by_subtopic_tracker.items()
    }

    recommendations = _build_recommendations(
        passed=passed,
        unanswered_question_ids=unanswered_question_ids,
        performance_by_subtopic=performance_by_subtopic,
        performance_by_type=performance_by_type,
    )

    per_question_results_payload = [
        result.model_dump()
        for result in per_question_results
    ]

    submitted_answers_payload = _build_submitted_answers_payload(payload.answers)
    total_time_spent_seconds = sum(
        answer.time_spent_seconds or 0
        for answer in payload.answers
    )

    attempt = QuizAttempt(
        user_id=current_user.id,
        source_lesson_id=payload.source_lesson_id,
        quiz_id=resolved_quiz_id,
        topic=resolved_topic,
        attempt_number=attempt_number,
        is_retry=is_retry,
        total_questions=total_questions,
        answered_questions=answered_questions,
        correct_answers=correct_answers,
        passing_score=payload.passing_score,
        score_percent=score_percent,
        passed=passed,
        time_spent_seconds=total_time_spent_seconds,
        unanswered_question_ids=sorted(unanswered_question_ids),
        submitted_answers=submitted_answers_payload,
        per_question_results=per_question_results_payload,
        performance_by_type=performance_by_type,
        performance_by_subtopic=performance_by_subtopic,
        recommendations=recommendations,
    )

    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    xp_amount = _calculate_quiz_xp(score_percent, passed, is_retry)
    gamification_payload: dict[str, Any] | None = None

    try:
        xp_update = await GamificationEngine.award_xp(db, str(current_user.id), amount=xp_amount)
        streak_update = await GamificationEngine.update_streak(db, str(current_user.id))
        gamification_payload = {**xp_update, **streak_update}

        attempt.xp_awarded = xp_update.get("xp_awarded", xp_amount)
        attempt.current_level_after = xp_update.get("current_level")
        await db.commit()
        await db.refresh(attempt)
    except Exception as exc:
        logger.warning("Gamification update failed for quiz attempt %s: %s", attempt.id, str(exc))
        gamification_payload = {
            "xp_awarded": 0,
            "error": "Gamification update failed",
        }

    return QuizEvaluationResponse(
        success=True,
        attempt_id=attempt.id,
        quiz_id=resolved_quiz_id,
        topic=resolved_topic,
        attempt_number=attempt_number,
        is_retry=is_retry,
        previous_best_score=previous_best_score,
        total_questions=total_questions,
        answered_questions=answered_questions,
        correct_answers=correct_answers,
        score_percent=score_percent,
        passed=passed,
        unanswered_question_ids=sorted(unanswered_question_ids),
        per_question_results=per_question_results,
        performance_by_type=performance_by_type,
        performance_by_subtopic=performance_by_subtopic,
        recommendations=recommendations,
        gamification=gamification_payload,
    )


@router.get("/attempts", response_model=list[QuizAttemptSummary])
async def list_quiz_attempts(
    limit: int = 20,
    offset: int = 0,
    topic: str | None = None,
    quiz_id: str | None = None,
    retries_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return quiz attempt history for the authenticated user."""
    safe_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)

    stmt = (
        select(QuizAttempt)
        .where(QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.created_at.desc())
        .offset(safe_offset)
        .limit(safe_limit)
    )

    if topic:
        stmt = stmt.where(QuizAttempt.topic == topic)
    if quiz_id:
        stmt = stmt.where(QuizAttempt.quiz_id == quiz_id)
    if retries_only:
        stmt = stmt.where(QuizAttempt.is_retry.is_(True))

    result = await db.execute(stmt)
    attempts = result.scalars().all()
    return [_serialize_attempt_summary(attempt) for attempt in attempts]


@router.get("/attempts/{attempt_id:uuid}", response_model=QuizAttemptDetail)
async def get_quiz_attempt(
    attempt_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return full details of a single quiz attempt."""
    result = await db.execute(
        select(QuizAttempt).where(
            QuizAttempt.id == attempt_id,
            QuizAttempt.user_id == current_user.id,
        )
    )
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz attempt not found")

    return _serialize_attempt_detail(attempt)


@router.get("/retries/{quiz_id}", response_model=list[QuizAttemptSummary])
async def get_quiz_retries(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all attempts for a quiz id to track retries and progress over time."""
    result = await db.execute(
        select(QuizAttempt)
        .where(
            QuizAttempt.user_id == current_user.id,
            QuizAttempt.quiz_id == quiz_id,
        )
        .order_by(QuizAttempt.attempt_number.asc(), QuizAttempt.created_at.asc())
    )
    attempts = result.scalars().all()
    return [_serialize_attempt_summary(attempt) for attempt in attempts]


@router.get("/analytics", response_model=QuizAnalyticsResponse)
async def get_quiz_analytics(
    topic: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregate quiz analytics for the authenticated user."""
    stmt = select(QuizAttempt).where(QuizAttempt.user_id == current_user.id)
    if topic:
        stmt = stmt.where(QuizAttempt.topic == topic)

    result = await db.execute(stmt)
    attempts = result.scalars().all()

    if not attempts:
        return QuizAnalyticsResponse(
            total_attempts=0,
            unique_quizzes=0,
            average_score=0.0,
            best_score=0.0,
            pass_rate=0.0,
            retry_attempts=0,
            retry_success_rate=0.0,
            first_attempt_pass_rate=0.0,
            improved_quiz_count=0,
            total_xp_from_quizzes=0,
            topic_analytics=[],
        )

    total_attempts = len(attempts)
    unique_quizzes = len({attempt.quiz_id for attempt in attempts})
    average_score = round(sum(attempt.score_percent for attempt in attempts) / total_attempts, 2)
    best_score = round(max(attempt.score_percent for attempt in attempts), 2)
    pass_rate = round((sum(1 for attempt in attempts if attempt.passed) / total_attempts) * 100, 2)

    retry_attempts_list = [attempt for attempt in attempts if attempt.is_retry]
    retry_attempts = len(retry_attempts_list)
    retry_success_rate = (
        round((sum(1 for attempt in retry_attempts_list if attempt.passed) / retry_attempts) * 100, 2)
        if retry_attempts > 0
        else 0.0
    )

    first_attempts = [attempt for attempt in attempts if attempt.attempt_number == 1]
    first_attempt_pass_rate = (
        round((sum(1 for attempt in first_attempts if attempt.passed) / len(first_attempts)) * 100, 2)
        if first_attempts
        else 0.0
    )

    attempts_by_quiz: dict[str, list[QuizAttempt]] = defaultdict(list)
    for attempt in attempts:
        attempts_by_quiz[attempt.quiz_id].append(attempt)

    improved_quiz_count = 0
    for quiz_attempts in attempts_by_quiz.values():
        ordered_attempts = sorted(
            quiz_attempts,
            key=lambda attempt: (attempt.attempt_number, attempt.created_at),
        )
        if len(ordered_attempts) <= 1:
            continue

        first_score = ordered_attempts[0].score_percent
        best_group_score = max(attempt.score_percent for attempt in ordered_attempts)
        if best_group_score > first_score:
            improved_quiz_count += 1

    topic_groups: dict[str, list[QuizAttempt]] = defaultdict(list)
    for attempt in attempts:
        topic_groups[attempt.topic].append(attempt)

    topic_analytics: list[QuizTopicAnalytics] = []
    for group_topic, group_attempts in sorted(topic_groups.items(), key=lambda item: item[0].lower()):
        group_total = len(group_attempts)
        group_avg_score = round(sum(item.score_percent for item in group_attempts) / group_total, 2)
        group_best_score = round(max(item.score_percent for item in group_attempts), 2)
        group_pass_rate = round((sum(1 for item in group_attempts if item.passed) / group_total) * 100, 2)
        group_retries = sum(1 for item in group_attempts if item.is_retry)

        topic_analytics.append(
            QuizTopicAnalytics(
                topic=group_topic,
                attempts=group_total,
                average_score=group_avg_score,
                best_score=group_best_score,
                pass_rate=group_pass_rate,
                retry_attempts=group_retries,
            )
        )

    total_xp_from_quizzes = sum(attempt.xp_awarded for attempt in attempts)

    return QuizAnalyticsResponse(
        total_attempts=total_attempts,
        unique_quizzes=unique_quizzes,
        average_score=average_score,
        best_score=best_score,
        pass_rate=pass_rate,
        retry_attempts=retry_attempts,
        retry_success_rate=retry_success_rate,
        first_attempt_pass_rate=first_attempt_pass_rate,
        improved_quiz_count=improved_quiz_count,
        total_xp_from_quizzes=total_xp_from_quizzes,
        topic_analytics=topic_analytics,
    )


@router.get("/analytics/lessons/{source_lesson_id:uuid}", response_model=LessonQuizAnalyticsResponse)
async def get_lesson_quiz_analytics(
    source_lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return quiz analytics scoped to a single saved lesson."""
    lesson_result = await db.execute(
        select(UserLesson.id).where(
            UserLesson.id == source_lesson_id,
            UserLesson.user_id == current_user.id,
        )
    )
    if lesson_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    attempts_result = await db.execute(
        select(QuizAttempt).where(
            QuizAttempt.user_id == current_user.id,
            QuizAttempt.source_lesson_id == source_lesson_id,
        )
    )
    attempts = attempts_result.scalars().all()

    if not attempts:
        return LessonQuizAnalyticsResponse(
            source_lesson_id=source_lesson_id,
            total_attempts=0,
            unique_quizzes=0,
            average_score=0.0,
            best_score=0.0,
            pass_rate=0.0,
            retry_attempts=0,
            retry_success_rate=0.0,
            first_attempt_pass_rate=0.0,
            improved_quiz_count=0,
            total_xp_from_quizzes=0,
            quizzes=[],
        )

    total_attempts = len(attempts)
    unique_quizzes = len({attempt.quiz_id for attempt in attempts})
    average_score = round(sum(attempt.score_percent for attempt in attempts) / total_attempts, 2)
    best_score = round(max(attempt.score_percent for attempt in attempts), 2)
    pass_rate = round((sum(1 for attempt in attempts if attempt.passed) / total_attempts) * 100, 2)

    retry_attempts_list = [attempt for attempt in attempts if attempt.is_retry]
    retry_attempts = len(retry_attempts_list)
    retry_success_rate = (
        round((sum(1 for attempt in retry_attempts_list if attempt.passed) / retry_attempts) * 100, 2)
        if retry_attempts > 0
        else 0.0
    )

    first_attempts = [attempt for attempt in attempts if attempt.attempt_number == 1]
    first_attempt_pass_rate = (
        round((sum(1 for attempt in first_attempts if attempt.passed) / len(first_attempts)) * 100, 2)
        if first_attempts
        else 0.0
    )

    attempts_by_quiz: dict[str, list[QuizAttempt]] = defaultdict(list)
    for attempt in attempts:
        attempts_by_quiz[attempt.quiz_id].append(attempt)

    improved_quiz_count = 0
    quiz_analytics: list[LessonQuizAnalyticsItem] = []

    for quiz_id, quiz_attempts in attempts_by_quiz.items():
        ordered_attempts = sorted(
            quiz_attempts,
            key=lambda attempt: (attempt.attempt_number, attempt.created_at),
        )

        if len(ordered_attempts) > 1:
            first_score = ordered_attempts[0].score_percent
            best_group_score = max(attempt.score_percent for attempt in ordered_attempts)
            if best_group_score > first_score:
                improved_quiz_count += 1

        quiz_total = len(ordered_attempts)
        quiz_avg_score = round(sum(item.score_percent for item in ordered_attempts) / quiz_total, 2)
        quiz_best_score = round(max(item.score_percent for item in ordered_attempts), 2)
        quiz_pass_rate = round((sum(1 for item in ordered_attempts if item.passed) / quiz_total) * 100, 2)
        quiz_retry_attempts = sum(1 for item in ordered_attempts if item.is_retry)
        latest_attempt = max(ordered_attempts, key=lambda item: item.created_at)

        quiz_analytics.append(
            LessonQuizAnalyticsItem(
                quiz_id=quiz_id,
                topic=latest_attempt.topic,
                attempts=quiz_total,
                average_score=quiz_avg_score,
                best_score=quiz_best_score,
                pass_rate=quiz_pass_rate,
                retry_attempts=quiz_retry_attempts,
                latest_attempt_at=latest_attempt.created_at,
            )
        )

    quiz_analytics.sort(key=lambda item: item.latest_attempt_at, reverse=True)
    total_xp_from_quizzes = sum(attempt.xp_awarded for attempt in attempts)

    return LessonQuizAnalyticsResponse(
        source_lesson_id=source_lesson_id,
        total_attempts=total_attempts,
        unique_quizzes=unique_quizzes,
        average_score=average_score,
        best_score=best_score,
        pass_rate=pass_rate,
        retry_attempts=retry_attempts,
        retry_success_rate=retry_success_rate,
        first_attempt_pass_rate=first_attempt_pass_rate,
        improved_quiz_count=improved_quiz_count,
        total_xp_from_quizzes=total_xp_from_quizzes,
        quizzes=quiz_analytics,
    )


@router.get("/health")
async def quiz_health() -> dict[str, Any]:
    """Health check for quiz service and orchestrator integration."""
    return {
        "status": "healthy",
        "service": "quiz-api",
        "orchestrator": "ExerciseOrchestrator",
    }
