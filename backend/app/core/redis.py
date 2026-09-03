"""Redis cache client."""

import redis.asyncio as redis

from app.core.config import get_settings

_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Get or create the async Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
