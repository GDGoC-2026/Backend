from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from Backend.api.deps import get_current_user
from Backend.models.user import User
from Backend.services.lightrag_service import get_lightrag_service


router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., description="User question for the learning copilot")


class ChatResponse(BaseModel):
    reply: str
    mode: str


@router.post("/ask", response_model=ChatResponse)
async def ask_copilot(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    message = req.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message must not be empty",
        )

    try:
        lightrag_service = get_lightrag_service()
        answer = await lightrag_service.query_knowledge(
            user_id=current_user.id,
            question=message,
            mode="hybrid",
        )
        return ChatResponse(reply=answer, mode="hybrid")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error querying chatbot: {str(e)}",
        )
