from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid

from Backend.api.deps import get_current_user
from Backend.db.session import get_db
from Backend.models.user import User
from Backend.models.course import CodeSession, Exercise
from Backend.models.coding import CodingProblem
from Backend.services.judge_controller import JudgeController


router = APIRouter()
judge_controller = JudgeController()


class CodeSubmission(BaseModel):
    source_code: str
    language_id: int
    exercise_id: uuid.UUID


class CodeSessionSave(BaseModel):
    current_code: str
    language_id: int
    exercise_id: Optional[uuid.UUID] = None
    coding_problem_id: Optional[uuid.UUID] = None


class CodeSessionUpdate(BaseModel):
    current_code: str
    language_id: int


@router.post("/execute")
async def execute_code(
    submission: CodeSubmission,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes a code snippet using Judge0 to validate programming exercises securely.
    """
    if current_user.subscription_tier not in ["developer", "enterprise"]:
        raise HTTPException(status_code=403, detail="Developer or Enterprise tier required for sandbox execution.")

    # Retrieve the exercise structure
    result = await db.execute(select(Exercise).where(Exercise.id == submission.exercise_id))
    exercise = result.scalar_one_or_none()

    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    try:
        result = await judge_controller.execute_code(
            submission.source_code,
            submission.language_id,
            exercise.expected_output
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions")
async def save_code_session(
    session_data: CodeSessionSave,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Save code state to resume later."""
    if session_data.exercise_id is None and session_data.coding_problem_id is None:
        raise HTTPException(
            status_code=422,
            detail="Either exercise_id or coding_problem_id is required",
        )

    if session_data.exercise_id is not None and session_data.coding_problem_id is not None:
        raise HTTPException(
            status_code=422,
            detail="Provide only one target: exercise_id or coding_problem_id",
        )

    if session_data.coding_problem_id is not None:
        problem_result = await db.execute(
            select(CodingProblem).where(
                CodingProblem.id == session_data.coding_problem_id,
                CodingProblem.user_id == current_user.id,
            )
        )
        problem = problem_result.scalar_one_or_none()
        if problem is None:
            raise HTTPException(status_code=404, detail="Coding problem not found")

    result = await db.execute(
        select(CodeSession).where(
            CodeSession.user_id == current_user.id,
            CodeSession.exercise_id == session_data.exercise_id,
            CodeSession.coding_problem_id == session_data.coding_problem_id,
        )
    )
    existing_session = result.scalar_one_or_none()

    if existing_session:
        existing_session.current_code = session_data.current_code
        existing_session.language_id = session_data.language_id
    else:
        new_session = CodeSession(
            user_id=current_user.id,
            exercise_id=session_data.exercise_id,
            coding_problem_id=session_data.coding_problem_id,
            current_code=session_data.current_code,
            language_id=session_data.language_id
        )
        db.add(new_session)

    await db.commit()
    return {"message": "Session saved successfully"}


@router.get("/sessions/{problem_id}")
async def get_coding_problem_session(
    problem_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get saved code session for a generated coding problem."""
    problem_result = await db.execute(
        select(CodingProblem).where(
            CodingProblem.id == problem_id,
            CodingProblem.user_id == current_user.id,
        )
    )
    problem = problem_result.scalar_one_or_none()
    if problem is None:
        raise HTTPException(status_code=404, detail="Coding problem not found")

    result = await db.execute(
        select(CodeSession).where(
            CodeSession.user_id == current_user.id,
            CodeSession.coding_problem_id == problem_id,
        )
    )
    existing_session = result.scalar_one_or_none()

    if existing_session is None:
        raise HTTPException(status_code=404, detail="Code session not found")

    return {
        "coding_problem_id": problem_id,
        "current_code": existing_session.current_code,
        "language_id": existing_session.language_id,
    }


@router.put("/sessions/{problem_id}")
async def upsert_coding_problem_session(
    problem_id: uuid.UUID,
    payload: CodeSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update code session for a generated coding problem."""
    problem_result = await db.execute(
        select(CodingProblem).where(
            CodingProblem.id == problem_id,
            CodingProblem.user_id == current_user.id,
        )
    )
    problem = problem_result.scalar_one_or_none()
    if problem is None:
        raise HTTPException(status_code=404, detail="Coding problem not found")

    result = await db.execute(
        select(CodeSession).where(
            CodeSession.user_id == current_user.id,
            CodeSession.coding_problem_id == problem_id,
        )
    )
    existing_session = result.scalar_one_or_none()

    if existing_session:
        existing_session.current_code = payload.current_code
        existing_session.language_id = payload.language_id
    else:
        db.add(
            CodeSession(
                user_id=current_user.id,
                exercise_id=None,
                coding_problem_id=problem_id,
                current_code=payload.current_code,
                language_id=payload.language_id,
            )
        )

    await db.commit()
    return {"message": "Session saved successfully"}
