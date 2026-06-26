# celery_app.py, includes celery app and its config

from celery import Celery
from app.core.config import settings as stngs

# Creating celery app
celery_app=Celery(
    "news_monitoring",
    broker=stngs.RABBITMQ_URL,
    backend=stngs.REDIS_URL,
    include=["app.tasks.analysis_tasks"]
)

# Updating app config
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)