"""Background task — run_investigation async entry point.

Provides a standard async function that wraps the orchestrator loop.
Replaces the previous Celery task. Designed to be submitted to the
TaskManager for managed execution.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def run_investigation_async(
    investigation_id: str,
) -> dict[str, Any]:
    """Execute the full investigation loop as an async background task.

    This is the main entry point for starting an investigation.
    It delegates to the orchestrator's async loop.

    Args:
        investigation_id: Investigation UUID to run.

    Returns:
        Summary dict with results.
    """
    from app.services.orchestrator import run_investigation_loop

    logger.info("Background task: starting investigation %s", investigation_id)

    try:
        # Build LLM callable from configured provider (None if unconfigured).
        from app.ai.client import get_llm_call_fn

        llm_fn = get_llm_call_fn()
        result = await run_investigation_loop(investigation_id, llm_call_fn=llm_fn)
    except Exception as exc:
        logger.exception(
            "Background task failed for investigation %s: %s", investigation_id, exc
        )
        # Update investigation status to error.
        try:
            await _set_investigation_error(investigation_id, str(exc))
        except Exception:
            logger.exception("Failed to set error status for %s", investigation_id)
        return {"error": str(exc), "investigation_id": investigation_id}

    logger.info(
        "Background task completed for investigation %s: %s",
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
