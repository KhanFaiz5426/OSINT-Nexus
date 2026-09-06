"""Tasks package — Celery background tasks (Phase 3+)."""

from app.tasks.celery_app import celery_app as celery

__all__ = ["celery"]
