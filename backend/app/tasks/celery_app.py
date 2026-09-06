"""Celery application configuration."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "osint_nexus",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.run_investigation"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    worker_concurrency=4,
    task_routes={
        "app.tasks.run_investigation": {"queue": "osint"},
        "app.tasks.collect_*": {"queue": "osint"},
        "app.tasks.ai_*": {"queue": "ai"},
        "app.tasks.generate_*": {"queue": "reports"},
    },
)
