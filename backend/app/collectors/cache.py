"""Collector cache — in-memory TTLCache for collector responses.

Provides a bounded, TTL-based cache for collector RawResult objects.
Replaces the previous Redis-backed implementation. Safe to access
directly under the single-event-loop model without locking.
"""

from __future__ import annotations

import logging

from cachetools import TTLCache

from app.models import RawResult

logger = logging.getLogger(__name__)


class CollectorCache:
    """In-memory TTL cache for collector RawResult objects.

    Keys are formatted as: {collector_name}:{target}:{target_type}
    Values are RawResult instances.

    Under the single-process asyncio model, TTLCache dictionary
    operations are atomic (they do not yield control) so no locking
    is required.
    """

    def __init__(
        self,
        maxsize: int = 10000,
        ttl: int = 86400,
    ) -> None:
        self._cache: TTLCache[str, RawResult] = TTLCache(
            maxsize=maxsize,
            ttl=ttl,
        )

    async def get(self, cache_key: str) -> RawResult | None:
        """Retrieve a cached result. Returns None on miss."""
        try:
            return self._cache.get(cache_key)
        except Exception:
            logger.debug("Cache get failed for %s", cache_key, exc_info=True)
            return None

    async def set(self, cache_key: str, result: RawResult, ttl: int | None = None) -> None:
        """Store a result in cache.

        Note: Per-key TTL override is not supported by cachetools.TTLCache;
        the cache-wide TTL is used. The ttl parameter is accepted for API
        compatibility but ignored.
        """
        try:
            self._cache[cache_key] = result
        except Exception:
            logger.debug("Cache set failed for %s", cache_key, exc_info=True)

    async def invalidate(self, cache_key: str) -> bool:
        """Remove a cached entry. Returns True if key existed."""
        try:
            if cache_key in self._cache:
                del self._cache[cache_key]
                return True
            return False
        except Exception:
            logger.debug("Cache invalidate failed for %s", cache_key, exc_info=True)
            return False

    async def clear_collector(self, collector_name: str) -> int:
        """Clear all cached results for a specific collector. Returns count removed."""
        try:
            prefix = f"{collector_name}:"
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)
        except Exception:
            logger.debug("Cache clear failed for %s", collector_name, exc_info=True)
            return 0

    @property
    def size(self) -> int:
        """Current number of entries in the cache."""
        return len(self._cache)

    @property
    def maxsize(self) -> int:
        """Maximum cache capacity."""
        return self._cache.maxsize


# ── Module-level singleton ────────────────────────────────────────────────────

_collector_cache: CollectorCache | None = None


def get_collector_cache() -> CollectorCache:
    """Get or create the global CollectorCache singleton."""
    global _collector_cache
    if _collector_cache is None:
        _collector_cache = CollectorCache()
    return _collector_cache


def reset_collector_cache() -> None:
    """Reset the global CollectorCache (for testing)."""
    global _collector_cache
    _collector_cache = None
