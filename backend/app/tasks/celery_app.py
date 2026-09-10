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
    task_time_limit=3600,
    task_soft_time_limit=1800,
    worker_concurrency=4,
    # Reliability improvements
    task_acks_late=True,  # Acknowledge tasks after completion, not before
    worker_prefetch_multiplier=1,  # Don't prefetch tasks (safer for long-running tasks)
    worker_max_tasks_per_child=50,  # Recycle workers to prevent memory leaks
    task_reject_on_worker_lost=True,  # Requeue tasks if worker crashes
    task_routes={
        "app.tasks.run_investigation": {"queue": "osint"},
        "app.tasks.collect_*": {"queue": "osint"},
        "app.tasks.ai_*": {"queue": "ai"},
        "app.tasks.generate_*": {"queue": "reports"},
    },
)
