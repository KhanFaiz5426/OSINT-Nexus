"""EventBus — in-process broadcast event distribution.

Provides a lightweight pub/sub EventBus that broadcasts events to all
subscribers for a given investigation_id. Designed to replace Redis
pub/sub for SSE distribution in the single-process desktop deployment.

Key semantics:
- Every subscriber receives every published event (broadcast, not load-balance).
- Slow subscribers are dropped (QueueFull) to prevent blocking the publisher.
- Subscriber queues are bounded (maxsize) and cleaned up on disconnect.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default maximum queue depth per subscriber before it is dropped.
DEFAULT_MAX_QUEUE_SIZE = 100


class EventBus:
    """Broadcast event bus for investigation SSE events.

    Structure: dict[investigation_id, set[asyncio.Queue]]
    - subscribe() creates a bounded Queue and adds it to the set.
    - publish() iterates over all queues and uses put_nowait().
    - If put_nowait() raises QueueFull, that subscriber is dropped.
    - unsubscribe() removes the queue; if the set empties, the key is deleted.
    """

    def __init__(self, max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._max_queue_size = max_queue_size

    def subscribe(self, investigation_id: str) -> asyncio.Queue[dict[str, Any]]:
        """Create a new subscriber queue for the given investigation.

        Returns the Queue that the SSE endpoint should await on.
        """
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._max_queue_size)
        if investigation_id not in self._subscribers:
            self._subscribers[investigation_id] = set()
        self._subscribers[investigation_id].add(queue)
        logger.debug(
            "EventBus: subscriber added for %s (total: %d)",
            investigation_id,
            len(self._subscribers[investigation_id]),
        )
        return queue

    def unsubscribe(self, investigation_id: str, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue. Cleans up empty sets."""
        subs = self._subscribers.get(investigation_id)
        if subs is not None:
            subs.discard(queue)
            if not subs:
                del self._subscribers[investigation_id]
        logger.debug("EventBus: subscriber removed for %s", investigation_id)

    def publish(self, investigation_id: str, event: dict[str, Any]) -> int:
        """Broadcast an event to all subscribers for the investigation.

        Returns the number of subscribers that received the event.
        Slow subscribers whose queues are full are silently dropped.
        """
        subs = self._subscribers.get(investigation_id)
        if not subs:
            return 0

        delivered = 0
        to_remove: list[asyncio.Queue] = []

        for queue in subs:
            try:
                queue.put_nowait(event)
                delivered += 1
            except asyncio.QueueFull:
                logger.warning(
                    "EventBus: dropping slow subscriber for %s (queue full)",
                    investigation_id,
                )
                to_remove.append(queue)

        # Remove slow subscribers outside the iteration.
        for queue in to_remove:
            subs.discard(queue)
        if not subs:
            del self._subscribers[investigation_id]

        return delivered

    @property
    def subscriber_count(self) -> int:
        """Total number of active subscriber queues across all investigations."""
        return sum(len(s) for s in self._subscribers.values())

    def get_investigation_subscriber_count(self, investigation_id: str) -> int:
        """Number of subscribers for a specific investigation."""
        return len(self._subscribers.get(investigation_id, set()))

    def clear(self) -> None:
        """Remove all subscribers. Used during shutdown."""
        self._subscribers.clear()


# ── Module-level singleton ────────────────────────────────────────────────────

_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get or create the global EventBus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global EventBus (for testing)."""
    global _event_bus
    if _event_bus is not None:
        _event_bus.clear()
    _event_bus = None
