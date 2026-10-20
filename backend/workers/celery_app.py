import os
from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "botbinance",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    worker_max_tasks_per_child=50,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
)

celery_app.conf.beat_schedule = {
    "cleanup-old-logs": {
        "task": "backend.workers.tasks.cleanup_old_logs",
        "schedule": crontab(hour=3, minute=0),
    },
    "daily-portfolio-report": {
        "task": "backend.workers.tasks.send_daily_report",
        "schedule": crontab(hour=23, minute=55),
    },
}