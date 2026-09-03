"""Collector cache — Redis-based cache layer for collector responses.

Provides a simple async cache keyed by collector name, target, and target type.
Supports per-collector TTL (default 24 hours).
"""

from __future__ import annotations

import json
import logging

import redis.asyncio as redis

from app.models import RawResult

logger = logging.getLogger(__name__)


class CollectorCache:
    """Redis-backed cache for collector RawResult objects.

    Keys are formatted as: osint:cache:{cache_key}
    Values are JSON-serialized RawResult dicts.
    """

    PREFIX = "osint:cache"

    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client

    def _make_key(self, cache_key: str) -> str:
        return f"{self.PREFIX}:{cache_key}"

    async def get(self, cache_key: str) -> RawResult | None:
        """Retrieve a cached result. Returns None on miss or error."""
        try:
            raw = await self._redis.get(self._make_key(cache_key))
            if raw is None:
                return None
            data = json.loads(raw)
            return RawResult(**data)
        except Exception:
            logger.debug("Cache get failed for %s", cache_key, exc_info=True)
            return None

    async def set(self, cache_key: str, result: RawResult, ttl: int = 86400) -> None:
        """Store a result in cache with TTL in seconds."""
        try:
            data = result.model_dump_json()
            await self._redis.set(self._make_key(cache_key), data, ex=ttl)
        except Exception:
            logger.debug("Cache set failed for %s", cache_key, exc_info=True)

    async def invalidate(self, cache_key: str) -> bool:
        """Remove a cached entry. Returns True if key existed."""
        try:
            return bool(await self._redis.delete(self._make_key(cache_key)))
        except Exception:
            logger.debug("Cache invalidate failed for %s", cache_key, exc_info=True)
            return False

    async def clear_collector(self, collector_name: str) -> int:
        """Clear all cached results for a specific collector. Returns count removed."""
        try:
            pattern = f"{self.PREFIX}:{collector_name}:*"
            count = 0
            async for key in self._redis.scan_iter(match=pattern):
                await self._redis.delete(key)
                count += 1
            return count
        except Exception:
            logger.debug("Cache clear failed for %s", collector_name, exc_info=True)
            return 0
