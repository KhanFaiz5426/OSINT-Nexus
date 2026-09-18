"""API routes — Server-Sent Events for real-time investigation updates.

Provides SSE endpoint for streaming investigation status and activity updates.
Uses the in-process EventBus for broadcast event distribution.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.core.event_bus import get_event_bus

router = APIRouter()
logger = logging.getLogger(__name__)


async def publish_investigation_event(
    investigation_id: str,
    event_type: str,
    data: dict[str, Any],
) -> None:
    """Publish an investigation event via the EventBus.

    This is called by the orchestrator at key pipeline stages.
    All subscribers for the investigation receive the event (broadcast).
    """
    try:
        bus = get_event_bus()
        event = {
            "type": event_type,
            "data": data,
        }
        delivered = bus.publish(investigation_id, event)
        logger.debug(
            "Published SSE event %s for %s (delivered to %d subscribers)",
            event_type,
            investigation_id,
            delivered,
        )
    except Exception as exc:
        logger.debug("Failed to publish SSE event: %s", exc)


@router.get("/investigations/{investigation_id}/events")
async def investigation_events(investigation_id: str, request: Request):
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
        bus = get_event_bus()
        queue = bus.subscribe(investigation_id)

        try:
            # Send initial connection event
            yield {
                "event": "connected",
                "data": json.dumps({"investigation_id": investigation_id}),
            }

            # Listen for events
            while True:
                # Check if client disconnected.
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=30.0,  # 30s heartbeat timeout
                    )
                    yield {
                        "event": event.get("type", "message"),
                        "data": json.dumps(event.get("data", {})),
                    }
                except TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({"status": "alive"}),
                    }
        except asyncio.CancelledError:
            pass
        finally:
            bus.unsubscribe(investigation_id, queue)

    return EventSourceResponse(event_generator())
