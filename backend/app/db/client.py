"""Database client — asyncpg connection pool for PostgreSQL."""

from collections.abc import AsyncGenerator

import asyncpg

from app.core.config import get_settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Get or create the asyncpg connection pool."""
    global _pool
    if _pool is None or _pool._closed:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool and not _pool._closed:
        await _pool.close()
        _pool = None


def reset_pool() -> None:
    """Reset the pool reference (for testing between event loops)."""
    global _pool
    _pool = None


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI dependency: yields a database connection."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn
