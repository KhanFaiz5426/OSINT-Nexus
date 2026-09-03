"""Retry logic — Exponential backoff for transient failures.

Retries on transient errors: HTTP 429 (rate limit), 503 (service unavailable),
connection timeouts, and network errors.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# HTTP status codes that should trigger a retry
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_retryable_error(exc: Exception) -> bool:
    """Determine if an exception is transient and worth retrying."""
    # httpx / httpcore errors
    exc_module = type(exc).__module__
    exc_name = type(exc).__name__

    if exc_module.startswith("httpx") or exc_module.startswith("httpcore"):
        if "TimeoutException" in exc_name or "ConnectError" in exc_name:
            return True
        if "HTTPStatusError" in exc_name:
            status_code = getattr(exc, "response", None)
            if status_code is not None:
                code = getattr(status_code, "status_code", 0)
                if code in RETRYABLE_STATUS_CODES:
                    return True

    # aiohttp errors
    if exc_module.startswith("aiohttp") and (
        "ClientError" in exc_name or "ServerTimeoutError" in exc_name
    ):
        return True

    # DNS errors (dnspython)
    if exc_module.startswith("dns") and ("Timeout" in exc_name or "NXDOMAIN" not in exc_name):
        return True

    # Generic network/IO errors
    return bool(isinstance(exc, (ConnectionError, TimeoutError, OSError)))


async def retry_with_backoff(
    func: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    **kwargs: Any,
) -> Any:
    """Execute a callable with exponential backoff retry.

    Args:
        func: Async callable to execute.
        *args: Positional arguments for func.
        max_attempts: Maximum number of attempts (1 = no retry).
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay cap in seconds.
        **kwargs: Keyword arguments for func.

    Returns:
        The return value of func on success.

    Raises:
        The last exception if all attempts fail.
    """
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc

            if attempt == max_attempts or not _is_retryable_error(exc):
                raise

            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            # Add jitter: 50%–100% of calculated delay
            import random

            delay = delay * (0.5 + random.random() * 0.5)

            logger.warning(
                "Attempt %d/%d failed for %s: %s. Retrying in %.1fs",
                attempt,
                max_attempts,
                func.__qualname__ if hasattr(func, "__qualname__") else str(func),
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]
