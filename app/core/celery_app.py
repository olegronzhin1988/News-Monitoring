# celery_app.py, includes celery app and its config

from celery import Celery
from celery.schedules import crontab 
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
# Setting app schedule, regular ctivity
celery_app.conf.beat_schedule ={
    "dispatch-due-analyses-every-minute": {
        "task":"dispatch_due_analyses",
        "schedule": crontab(minute="*")
    },
    "send-pending-alerts-every-minute": {
    "task":"send_pending_alerts",
    "schedule": crontab(minute="*")
    },
}