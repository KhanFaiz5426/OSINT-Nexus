"""Tasks package — async background tasks."""

from app.tasks.run_investigation import run_investigation_async

__all__ = ["run_investigation_async"]
