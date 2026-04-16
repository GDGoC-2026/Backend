from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from Backend.api.deps import get_current_user
from Backend.db.session import get_db
from Backend.models.user import User
from Backend.schemas.user import UserProfile


router = APIRouter()


class SubscriptionUpdate(BaseModel):
    new_tier: str # freemium, pro, developer, enterprise


@router.get("/profile", response_model=UserProfile)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/subscription", response_model=UserProfile)
async def update_subscription(
    payload: SubscriptionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user's subscription tier."""
    if payload.new_tier not in ["freemium", "pro", "developer", "enterprise"]:
        raise HTTPException(status_code=400, detail="Invalid subscription tier")
        
    current_user.subscription_tier = payload.new_tier
    await db.commit()
    await db.refresh(current_user)
    return current_user
