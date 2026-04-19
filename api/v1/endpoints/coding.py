import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Backend.api.deps import get_current_user
from Backend.db.session import get_db
from Backend.models.coding import CodingAttempt, CodingProblem
from Backend.models.user import User
from Backend.models.user_lesson import UserLesson
from Backend.schemas.coding import (
    CodeRunRequest,
    CodeRunResponse,
    CodeSubmitRequest,
    CodeSubmitResponse,
    CodingAttemptSummary,
    CodingAttemptsResponse,
    CodingProblemDetail,
    CodingProblemGenerateRequest,
    CodingProblemSummary,
    CodingProblemsGenerationResponse,
    CodingTestCase,
    TestCaseResult,
)
from Backend.services.gamification import GamificationEngine
from Backend.services.judge_controller import JudgeController
from Backend.services.workflows.agents.coding_task_creator import CodingTaskCreatorAgent


router = APIRouter()
judge_controller = JudgeController()


def _ensure_sandbox_access(current_user: User) -> None:
    # Temporary: allow sandbox execution for all tiers while coding workspace is being integrated.
    # TODO: restore tier-based access control once frontend gating and UX are in place.
    return None


def _problem_to_summary(problem: CodingProblem) -> CodingProblemSummary:
    return CodingProblemSummary(
        id=problem.id,
        source_lesson_id=problem.source_lesson_id,
        topic=problem.topic,
        title=problem.title,
        language=problem.language,
        language_id=problem.language_id,
        difficulty=problem.difficulty,
        include_in_lesson=problem.include_in_lesson,
        created_at=problem.created_at,
        updated_at=problem.updated_at,
    )


def _problem_to_detail(
    problem: CodingProblem,
    include_solution: bool,
    include_hidden_tests: bool,
) -> CodingProblemDetail:
    test_cases = [
        CodingTestCase(**case)
        for case in (problem.test_cases or [])
        if include_hidden_tests or not bool(case.get("is_hidden", False))
    ]

    return CodingProblemDetail(
        **_problem_to_summary(problem).model_dump(),
        instructions=problem.instructions,
        starter_code=problem.starter_code,
        solution_code=problem.solution_code if include_solution else None,
        test_cases=test_cases,
        hints=problem.hints or [],
    )


def _attempt_to_summary(attempt: CodingAttempt) -> CodingAttemptSummary:
    return CodingAttemptSummary(
        id=attempt.id,
        coding_problem_id=attempt.coding_problem_id,
        mode=attempt.mode,
        language_id=attempt.language_id,
        overall_status=attempt.overall_status,
        passed=attempt.passed,
        total_tests=attempt.total_tests,
        passed_tests=attempt.passed_tests,
        created_at=attempt.created_at,
    )


async def _get_user_lesson_or_404(
    db: AsyncSession,
    lesson_id: UUID,
    user_id: UUID,
) -> UserLesson:
    result = await db.execute(
        select(UserLesson).where(
            UserLesson.id == lesson_id,
            UserLesson.user_id == user_id,
        )
    )
    lesson = result.scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return lesson


async def _get_coding_problem_or_404(
    db: AsyncSession,
    problem_id: UUID,
    user_id: UUID,
) -> CodingProblem:
    result = await db.execute(
        select(CodingProblem).where(
            CodingProblem.id == problem_id,
            CodingProblem.user_id == user_id,
        )
    )
    problem = result.scalar_one_or_none()
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coding problem not found")
    return problem


def _extract_subtopics(pages: list[dict[str, Any]]) -> list[str]:
    subtopics: list[str] = []
    skip_page_types = {"overview", "quiz", "flashcards", "mindmap", "resources", "coding"}

    for page in pages:
        page_type = str(page.get("page_type", ""))
        title = str(page.get("title", "")).strip()
        if title and page_type not in skip_page_types:
            subtopics.append(title)

    return subtopics[:6]


def _extract_learning_objectives(pages: list[dict[str, Any]], topic: str) -> list[str]:
    for page in pages:
        data = page.get("data")
        if not isinstance(data, dict):
            continue

        lesson_obj = data.get("lesson")
        if isinstance(lesson_obj, dict):
            objectives = lesson_obj.get("learning_objectives")
            if isinstance(objectives, list) and objectives:
                return [str(item) for item in objectives if str(item).strip()][:8]

    return [
        f"Understand the fundamentals of {topic}",
        f"Apply {topic} concepts through implementation",
    ]


def _sanitize_test_case_result(raw: dict[str, Any]) -> TestCaseResult:
    is_hidden = bool(raw.get("is_hidden", False))
    return TestCaseResult(
        index=int(raw.get("index", 0)),
        input="<hidden>" if is_hidden else str(raw.get("input", "")),
        expected_output="<hidden>" if is_hidden else str(raw.get("expected_output", "")),
        actual_output=raw.get("actual_output"),
        passed=bool(raw.get("passed", False)),
        status=raw.get("status"),
        stderr=raw.get("stderr"),
        compile_output=raw.get("compile_output"),
        time=raw.get("time"),
        memory=raw.get("memory"),
        is_hidden=is_hidden,
    )


async def _persist_submit_attempt(
    db: AsyncSession,
    current_user: User,
    problem: CodingProblem,
    source_code: str,
    language_id: int,
    evaluation_result: dict[str, Any],
) -> CodingAttempt:
    passed = bool(evaluation_result.get("passed", False))
    total_tests = int(evaluation_result.get("total_tests", 0))
    passed_tests = int(evaluation_result.get("passed_tests", 0))

    attempt = CodingAttempt(
        user_id=current_user.id,
        coding_problem_id=problem.id,
        mode="submit",
        source_code=source_code,
        language_id=language_id,
        overall_status=str(evaluation_result.get("status", "Unknown")),
        passed=passed,
        total_tests=total_tests,
        passed_tests=passed_tests,
        result_summary={
            "passed": passed,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
        },
        raw_result=evaluation_result,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt


@router.post(
    "/lessons/{lesson_id:uuid}/coding-problems/generate",
    response_model=CodingProblemsGenerationResponse,
)
async def generate_coding_problems_for_lesson(
    lesson_id: UUID,
    payload: CodingProblemGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lesson = await _get_user_lesson_or_404(db, lesson_id, current_user.id)

    if payload.decision_mode == "skip":
        return CodingProblemsGenerationResponse(
            success=True,
            include_coding_exercises=False,
            reason="Coding generation was skipped by client decision mode.",
            generated_count=0,
            problems=[],
        )

    pages = lesson.pages or []
    subtopics = _extract_subtopics(pages)
    if not subtopics:
        subtopics = [lesson.topic]

    objectives = _extract_learning_objectives(pages, lesson.topic)

    agent = CodingTaskCreatorAgent()
    result = await agent.run(
        {
            "topic": lesson.topic,
            "subject": lesson.topic,
            "subtopics": subtopics,
            "learning_objectives": objectives,
            "difficulty": "intermediate",
            "max_tasks": payload.max_problems,
            "decision_mode": payload.decision_mode,
        }
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.get("error", "Failed to generate coding problems"),
        )

    data = result.get("data", {})
    include_coding = bool(data.get("include_coding_exercises", False))
    reason = str(data.get("decision_reason", "No decision reason provided"))

    if not include_coding:
        return CodingProblemsGenerationResponse(
            success=True,
            include_coding_exercises=False,
            reason=reason,
            generated_count=0,
            problems=[],
        )

    coding_tasks = data.get("coding_tasks", [])
    if not coding_tasks:
        return CodingProblemsGenerationResponse(
            success=True,
            include_coding_exercises=False,
            reason="Coding was selected but no tasks were generated.",
            generated_count=0,
            problems=[],
        )

    created_problems: list[CodingProblem] = []
    for task in coding_tasks:
        problem = CodingProblem(
            user_id=current_user.id,
            source_lesson_id=lesson.id,
            topic=lesson.topic,
            title=str(task.get("title", f"Coding Task: {lesson.topic}")),
            instructions=str(task.get("instructions", "")),
            language=str(task.get("language", "python")),
            language_id=int(task.get("language_id", 71)),
            starter_code=str(task.get("starting_code", "")),
            solution_code=str(task.get("solution_code")) if task.get("solution_code") is not None else None,
            test_cases=task.get("test_cases", []),
            hints=[str(item) for item in task.get("hints", [])],
            difficulty=str(task.get("difficulty", "intermediate")),
            include_in_lesson=True,
        )
        db.add(problem)
        created_problems.append(problem)

    await db.commit()
    for problem in created_problems:
        await db.refresh(problem)

    return CodingProblemsGenerationResponse(
        success=True,
        include_coding_exercises=True,
        reason=reason,
        generated_count=len(created_problems),
        problems=[_problem_to_summary(problem) for problem in created_problems],
    )


@router.get(
    "/lessons/{lesson_id:uuid}/coding-problems",
    response_model=list[CodingProblemSummary],
)
async def list_lesson_coding_problems(
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_user_lesson_or_404(db, lesson_id, current_user.id)

    result = await db.execute(
        select(CodingProblem)
        .where(
            CodingProblem.user_id == current_user.id,
            CodingProblem.source_lesson_id == lesson_id,
        )
        .order_by(CodingProblem.created_at.desc())
    )

    problems = result.scalars().all()
    return [_problem_to_summary(problem) for problem in problems]


@router.get(
    "/coding-problems/{problem_id:uuid}",
    response_model=CodingProblemDetail,
)
async def get_coding_problem(
    problem_id: UUID,
    include_solution: bool = Query(default=False),
    include_hidden_tests: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    problem = await _get_coding_problem_or_404(db, problem_id, current_user.id)
    return _problem_to_detail(
        problem=problem,
        include_solution=include_solution,
        include_hidden_tests=include_hidden_tests,
    )


@router.post(
    "/coding-problems/{problem_id:uuid}/run",
    response_model=CodeRunResponse,
)
async def run_coding_problem(
    problem_id: UUID,
    payload: CodeRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_sandbox_access(current_user)
    problem = await _get_coding_problem_or_404(db, problem_id, current_user.id)
    language_id = payload.language_id or problem.language_id

    stdin = payload.stdin
    if stdin is None:
        public_case = next(
            (case for case in (problem.test_cases or []) if not bool(case.get("is_hidden", False))),
            None,
        )
        stdin = str(public_case.get("input", "")) if public_case else ""

    run_result = await judge_controller.run_code(
        source_code=payload.source_code,
        language_id=language_id,
        stdin=stdin,
    )

    status_data = run_result.get("status", {})
    attempt = CodingAttempt(
        user_id=current_user.id,
        coding_problem_id=problem.id,
        mode="run",
        source_code=payload.source_code,
        language_id=language_id,
        overall_status=status_data.get("description"),
        passed=bool(status_data.get("id") == 3),
        total_tests=0,
        passed_tests=0,
        result_summary={"stdin": stdin},
        raw_result=run_result,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    return CodeRunResponse(
        success=True,
        attempt_id=attempt.id,
        status=status_data.get("description"),
        stdout=run_result.get("stdout"),
        stderr=run_result.get("stderr"),
        compile_output=run_result.get("compile_output"),
        time=run_result.get("time"),
        memory=run_result.get("memory"),
        raw_result=run_result,
    )


@router.post(
    "/coding-problems/{problem_id:uuid}/submit",
    response_model=CodeSubmitResponse,
)
async def submit_coding_problem(
    problem_id: UUID,
    payload: CodeSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_sandbox_access(current_user)
    problem = await _get_coding_problem_or_404(db, problem_id, current_user.id)
    language_id = payload.language_id or problem.language_id

    test_cases = problem.test_cases or []
    if not test_cases:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Coding problem has no test cases",
        )

    try:
        evaluation_result = await judge_controller.evaluate_test_cases(
            source_code=payload.source_code,
            language_id=language_id,
            test_cases=test_cases,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Judge service unavailable or execution failed: {str(exc)}",
        ) from exc

    attempt = await _persist_submit_attempt(
        db=db,
        current_user=current_user,
        problem=problem,
        source_code=payload.source_code,
        language_id=language_id,
        evaluation_result=evaluation_result,
    )

    passed = bool(evaluation_result.get("passed", False))
    total_tests = int(evaluation_result.get("total_tests", 0))
    passed_tests = int(evaluation_result.get("passed_tests", 0))

    # Count coding submit as learning activity for streak; XP only when accepted.
    await GamificationEngine.update_streak(db, str(current_user.id))
    if passed:
        await GamificationEngine.award_xp(db, str(current_user.id), amount=15)

    case_results = [
        _sanitize_test_case_result(result)
        for result in evaluation_result.get("results", [])
    ]

    return CodeSubmitResponse(
        success=True,
        attempt_id=attempt.id,
        passed=passed,
        total_tests=total_tests,
        passed_tests=passed_tests,
        status=evaluation_result.get("status"),
        results=case_results,
    )


@router.post("/coding-problems/{problem_id:uuid}/submit/stream")
async def submit_coding_problem_stream(
    problem_id: UUID,
    payload: CodeSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_sandbox_access(current_user)
    problem = await _get_coding_problem_or_404(db, problem_id, current_user.id)
    language_id = payload.language_id or problem.language_id
    test_cases = problem.test_cases or []

    if not test_cases:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Coding problem has no test cases",
        )

    async def generate_sse():
        try:
            total_tests = len(test_cases)
            passed_tests = 0
            case_results: list[dict[str, Any]] = []

            yield f"data: {json.dumps({'status': 'started', 'total_tests': total_tests})}\n\n"

            async for case_result in judge_controller.iter_test_case_results(
                source_code=payload.source_code,
                language_id=language_id,
                test_cases=test_cases,
            ):
                case_results.append(case_result)
                if bool(case_result.get("passed", False)):
                    passed_tests += 1

                safe_case_result = _sanitize_test_case_result(case_result).model_dump(mode="json")
                case_payload = {
                    "status": "case",
                    "case_result": safe_case_result,
                    "passed_tests": passed_tests,
                    "total_tests": total_tests,
                }
                yield f"data: {json.dumps(case_payload)}\n\n"

            passed = total_tests > 0 and passed_tests == total_tests
            overall_status = "Accepted" if passed else "Wrong Answer"
            for result in case_results:
                if result.get("compile_output"):
                    overall_status = "Compilation Error"
                    break
                if result.get("status") and str(result.get("status")).lower() not in {
                    "accepted",
                    "wrong answer",
                } and not result.get("passed", False):
                    overall_status = str(result.get("status"))
                    break

            evaluation_result = {
                "passed": passed,
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "status": overall_status,
                "results": case_results,
            }

            attempt = await _persist_submit_attempt(
                db=db,
                current_user=current_user,
                problem=problem,
                source_code=payload.source_code,
                language_id=language_id,
                evaluation_result=evaluation_result,
            )

            await GamificationEngine.update_streak(db, str(current_user.id))
            if passed:
                await GamificationEngine.award_xp(db, str(current_user.id), amount=15)

            sanitized_results = [
                _sanitize_test_case_result(result).model_dump(mode="json")
                for result in case_results
            ]
            completed_payload = {
                "status": "completed",
                "attempt_id": str(attempt.id),
                "passed": passed,
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "result_status": overall_status,
                "results": sanitized_results,
            }
            yield f"data: {json.dumps(completed_payload)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'status': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/coding-problems/{problem_id:uuid}/attempts",
    response_model=CodingAttemptsResponse,
)
async def list_coding_problem_attempts(
    problem_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_coding_problem_or_404(db, problem_id, current_user.id)

    result = await db.execute(
        select(CodingAttempt)
        .where(
            CodingAttempt.user_id == current_user.id,
            CodingAttempt.coding_problem_id == problem_id,
        )
        .order_by(CodingAttempt.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    attempts = result.scalars().all()
    return CodingAttemptsResponse(attempts=[_attempt_to_summary(attempt) for attempt in attempts])
