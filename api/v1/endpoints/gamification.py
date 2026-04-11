from typing import List, Dict
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from Backend.db.session import get_db
from Backend.services.gamification import GamificationEngine

router = APIRouter()

@router.get("/leaderboard", response_model=List[Dict])
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    """Fetch the top users by total XP."""
    limit = 10
    leaderboard = await GamificationEngine.get_leaderboard(db, limit)
    return leaderboard
