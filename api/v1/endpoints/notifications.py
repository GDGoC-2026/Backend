from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from Backend.api.deps import get_current_user
from Backend.db.session import get_db
from Backend.models.user import User
from Backend.models.learning import PushSubscription

router = APIRouter()

class PushSubCreate(BaseModel):
    endpoint: str
    keys: dict


@router.post("/subscribe", status_code=201)
async def subscribe_push(
    sub: PushSubCreate, 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if exists
    result = await db.execute(select(PushSubscription).where(PushSubscription.endpoint == sub.endpoint))
    existing = result.scalar_one_or_none()
    
    if not existing:
        new_sub = PushSubscription(
            user_id=current_user.id,
            endpoint=sub.endpoint,
            p256dh=sub.keys.get("p256dh", ""),
            auth=sub.keys.get("auth", "")
        )
        db.add(new_sub)
        await db.commit()
        
    return {"message": "Successfully subscribed to learning reminders."}
