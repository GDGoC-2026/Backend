import asyncio
import json
import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from pywebpush import webpush, WebPushException

from Backend.core.celery_app import celery_app
from Backend.core.config import settings
from Backend.db.session import AsyncSessionLocal
from sqlalchemy import select
from Backend.models.learning import Flashcard, PushSubscription

load_dotenv(dotenv_path="../.env")

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_CLAIMS = {
    "sub": os.getenv("VAPID_SUBJECT"),
    "exp": int(time.time()) + 12 * 60 * 60
}

async def _send_due_review_notifications_async() -> dict:
    """Finds users with due cards and sends a push notification."""
    now = datetime.now(timezone.utc)
    sent_count = 0
    failed_count = 0
    
    async with AsyncSessionLocal() as db:
        # Find users who have cards due right now
        stmt = select(Flashcard.user_id).where(Flashcard.due_date <= now).distinct()
        result = await db.execute(stmt)
        users_with_due_cards = result.scalars().all()
        
        for user_id in users_with_due_cards:
            # Get their push subscriptions
            sub_stmt = select(PushSubscription).where(PushSubscription.user_id == user_id)
            subs = await db.execute(sub_stmt)
            
            for sub in subs.scalars().all():
                try:
                    webpush(
                        subscription_info={
                            "endpoint": sub.endpoint,
                            "keys": {"p256dh": sub.p256dh, "auth": sub.auth}
                        },
                        data=json.dumps({
                            "title": "Time to Practice!",
                            "body": "Your personalized AI lesson is ready. Protect your streak!",
                            "url": "/dashboard/learn"
                        }),
                        vapid_private_key=VAPID_PRIVATE_KEY,
                        vapid_claims=VAPID_CLAIMS
                    )
                    sent_count += 1
                except WebPushException as ex:
                    failed_count += 1
                    print(f"Push failed: {repr(ex)}")

    return {
        "users_with_due_cards": len(users_with_due_cards),
        "notifications_sent": sent_count,
        "notifications_failed": failed_count,
    }


@celery_app.task
def send_due_review_notifications() -> dict:
    return asyncio.run(_send_due_review_notifications_async())
