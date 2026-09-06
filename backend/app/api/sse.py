"""API routes — Server-Sent Events for real-time investigation updates.

Provides SSE endpoint for streaming investigation status and activity updates.
Uses Redis pub/sub for event distribution from Celery worker to API server.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.core.redis import get_redis

router = APIRouter()
logger = logging.getLogger(__name__)


async def publish_investigation_event(
    investigation_id: str,
    event_type: str,
    data: dict[str, Any],
) -> None:
    """Publish an investigation event to Redis for SSE distribution.

    This is called by the orchestrator at key pipeline stages.
    """
    try:
        redis = await get_redis()
        channel = f"investigation:{investigation_id}:events"
        event = {
            "type": event_type,
            "data": data,
        }
        await redis.publish(channel, json.dumps(event))
    except Exception as exc:
        logger.debug("Failed to publish SSE event: %s", exc)


@router.get("/investigations/{investigation_id}/events")
async def investigation_events(investigation_id: str):
    """Stream real-time investigation events via Server-Sent Events.

    Events include:
    - investigation_started
    - collector_dispatched
    - pivot_round_completed
    - investigation_completed
    - investigation_error
    - activity_logged
    """
    from app.db.client import get_pool

    # Verify investigation exists
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM investigations WHERE id = $1",
            investigation_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    async def event_generator():
        redis = await get_redis()
        pubsub = redis.pubsub()
        channel = f"investigation:{investigation_id}:events"
        await pubsub.subscribe(channel)

        try:
            # Send initial connection event
            yield {
                "event": "connected",
                "data": json.dumps({"investigation_id": investigation_id}),
            }

            # Listen for events
            while True:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True),
                    timeout=30.0,  # 30s heartbeat timeout
                )
                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    yield {
                        "event": data.get("type", "message"),
                        "data": json.dumps(data.get("data", {})),
                    }
        except asyncio.TimeoutError:
            # Send heartbeat to keep connection alive
            yield {
                "event": "heartbeat",
                "data": json.dumps({"status": "alive"}),
            }
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return EventSourceResponse(event_generator())
