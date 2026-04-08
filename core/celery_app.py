from celery import Celery
from Backend.core.config import settings

celery_app = Celery(
    "knowledge_bus",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["Backend.workers.ingestion_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)