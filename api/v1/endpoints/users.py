from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from Backend.api.deps import get_current_user
from Backend.db.session import get_db
from Backend.models.user import User
from Backend.schemas.user import UserProfile

router = APIRouter()

@router.get("/profile", response_model=UserProfile)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user
