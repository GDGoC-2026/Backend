from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from Backend.api.deps import get_current_user
from Backend.db.session import get_db
from Backend.models.user import User
from Backend.models.gamification import UserStats, DailyStreak
from Backend.services.gamification import GamificationEngine


router = APIRouter()


@router.get("/my-stats")
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetch current user's gamification stats."""
    stats_query = await db.execute(select(UserStats).where(UserStats.user_id == current_user.id))
    stats = stats_query.scalar_one_or_none()
    
    streak_query = await db.execute(select(DailyStreak).where(DailyStreak.user_id == current_user.id))
    streak = streak_query.scalar_one_or_none()
    
    if not stats:
        return {"total_xp": 0, "current_level": 1, "longest_streak": 0, "current_streak_date": None}
        
    return {
        "total_xp": stats.total_xp,
        "current_level": stats.current_level,
        "longest_streak": stats.longest_streak,
        "last_activity_date": streak.last_activity_date if streak else None
    }


@router.get("/leaderboard", response_model=List[Dict])
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    """Fetch the top users by total XP."""
    limit = 10
    leaderboard = await GamificationEngine.get_leaderboard(db, limit)
    return leaderboard
