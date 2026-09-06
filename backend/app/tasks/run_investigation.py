"""Celery task — run_investigation background task.

Task 6.6: Full investigation loop as a Celery background task.
Wraps the orchestrator with Celery lifecycle management.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine in a Celery task (sync context).

    Resets all connection pools before each call so drivers bind to the new event loop.
    """
    from app.core.redis import reset_redis
    from app.db.client import reset_pool
    from app.graph.client import reset_driver

    reset_pool()
    reset_driver()
    reset_redis()
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="app.tasks.run_investigation", max_retries=1)
def run_investigation_task(
    self,
    investigation_id: str,
) -> dict[str, Any]:
    """Execute the full investigation loop as a background Celery task.

    This is the main entry point for starting an investigation.
    It delegates to the orchestrator's async loop.

    Args:
        investigation_id: Investigation UUID to run.

    Returns:
        Summary dict with results.
    """
    from app.services.orchestrator import run_investigation_loop

    logger.info("Celery task: starting investigation %s", investigation_id)

    try:
        # Build LLM callable from configured provider (None if unconfigured).
        from app.ai.client import get_llm_call_fn

        llm_fn = get_llm_call_fn()
        result = _run_async(run_investigation_loop(investigation_id, llm_call_fn=llm_fn))
    except Exception as exc:
        logger.exception("Celery task failed for investigation %s: %s", investigation_id, exc)
        # Update investigation status to error.
        try:
            _run_async(_set_investigation_error(investigation_id, str(exc)))
        except Exception:
            logger.exception("Failed to set error status for %s", investigation_id)
        return {"error": str(exc), "investigation_id": investigation_id}

    logger.info(
        "Celery task completed for investigation %s: %s",
        investigation_id,
        result.get("status"),
    )
    return result


async def _set_investigation_error(investigation_id: str, error: str) -> None:
    """Set investigation status to error."""
    from datetime import UTC, datetime

    from app.db.client import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE investigations
            SET status = 'error', updated_at = $1
            WHERE id = $2
            """,
            datetime.now(UTC),
            investigation_id,
        )
