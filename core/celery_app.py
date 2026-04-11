from celery import Celery
from celery.schedules import crontab
from Backend.core.config import settings

celery_app = Celery(
    "knowledge_bus",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["Backend.workers.ingestion_tasks", "Backend.workers.notification_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    'send-review-reminders-every-hour': {
        'task': 'Backend.workers.notification_tasks.send_due_review_notifications',
        'schedule': crontab(minute=0), # Runs at the top of every hour
    },
}
