from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from Backend.api.deps import get_current_user
from Backend.models.user import User
from Backend.services.judge_controller import JudgeController

router = APIRouter()
judge_controller = JudgeController()

class CodeSubmission(BaseModel):
    source_code: str
    language_id: int
    expected_output: str

@router.post("/execute")
async def execute_code(
    submission: CodeSubmission,
    current_user: User = Depends(get_current_user)
):
    """
    Executes a code snippet using Judge0 to validate programming exercises.
    """
    try:
        result = await judge_controller.execute_code(
            submission.source_code,
            submission.language_id,
            submission.expected_output
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
