"""Rate limiter — Token bucket algorithm for per-collector rate limiting.

Each collector gets its own limiter instance. The token bucket allows
burst traffic up to the burst size while enforcing an average rate.
"""

from __future__ import annotations

import asyncio
import time


class TokenBucketRateLimiter:
    """Async token bucket rate limiter.

    Args:
        rate: Tokens added per second (sustained rate).
        burst: Maximum tokens the bucket can hold (burst capacity).
    """

    def __init__(self, rate: float, burst: int) -> None:
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_refill = now

    async def acquire(self, tokens: int = 1) -> float:
        """Wait until tokens are available, then consume them.

        Returns the time in seconds waited.
        """
        waited = 0.0
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return waited
                # Calculate wait time for next token
                wait_time = (tokens - self._tokens) / self._rate
                waited += wait_time
                await asyncio.sleep(wait_time)

    @property
    def available_tokens(self) -> float:
        """Current number of available tokens (approximate)."""
        self._refill()
        return self._tokens
