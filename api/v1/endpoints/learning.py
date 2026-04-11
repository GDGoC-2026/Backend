from datetime import datetime, timezone
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from Backend.api.deps import get_current_user
from Backend.db.session import get_db
from Backend.models.user import User
from Backend.models.learning import Flashcard
from Backend.services.fsrs import FSRSScheduler
from Backend.services.gamification import GamificationEngine


router = APIRouter()
fsrs_scheduler = FSRSScheduler()


class ReviewSubmit(BaseModel):
    grade: int  # 1: Again, 2: Hard, 3: Good, 4: Easy


class FlashcardResponse(BaseModel):
    id: UUID
    front_content: str
    back_content: str
    
    class Config:
        from_attributes = True


@router.get("/due", response_model=List[FlashcardResponse])
async def get_due_flashcards(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch all flashcards that are currently due for review."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Flashcard)
        .where(Flashcard.user_id == current_user.id, Flashcard.due_date <= now)
        .order_by(Flashcard.due_date.asc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/{card_id}/review")
async def submit_review(
    card_id: UUID,
    review: ReviewSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit a grade (1-4) for a flashcard to update its FSRS schedule."""
    if review.grade not in [1, 2, 3, 4]:
        raise HTTPException(status_code=400, detail="Grade must be between 1 and 4")

    result = await db.execute(select(Flashcard).where(Flashcard.id == card_id, Flashcard.user_id == current_user.id))
    card = result.scalar_one_or_none()
    
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    # Calculate new FSRS parameters
    new_due_date, new_stability, new_difficulty = fsrs_scheduler.calculate_next_review(card, review.grade)
    
    # Update card stats
    card.last_review = datetime.now(timezone.utc)
    card.due_date = new_due_date
    card.stability = new_stability
    card.difficulty = new_difficulty
    card.reps += 1
    if review.grade == 1:
        card.lapses += 1
        
    # Award Gamification XP for studying
    xp_update = await GamificationEngine.award_xp(db, str(current_user.id), amount=5)
    streak_update = await GamificationEngine.update_streak(db, str(current_user.id))

    await db.commit()
    
    return {
        "message": "Review saved",
        "next_due": new_due_date,
        "gamification": {**xp_update, **streak_update}
    }
