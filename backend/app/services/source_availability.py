"""Source availability — evidence-based URL accessibility checking.

Provides async URL availability verification using HEAD requests with
rate limiting, caching, and graceful degradation. Respects existing
collector infrastructure (rate limits, cache, request budgets).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from cachetools import TTLCache

from app.collectors.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)

# ── Availability states ──────────────────────────────────────────────────────

SOURCE_AVAILABILITY_STATES = {
    "available",
    "not_found",
    "redirected",
    "access_denied",
    "auth_required",
    "rate_limited",
    "temporarily_unavailable",
    "blocked",
    "unknown",
}


def map_http_status(status_code: int, is_redirect: bool = False) -> str:
    """Map HTTP status code to availability state."""
    if 200 <= status_code < 300:
        return "available"
    if status_code in (301, 302, 307, 308):
        return "redirected"
    if status_code == 403:
        return "access_denied"
    if status_code == 404:
        return "not_found"
    if status_code == 401:
        return "auth_required"
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code < 600:
        return "temporarily_unavailable"
    return "unknown"


# ── Cache ─────────────────────────────────────────────────────────────────────

CACHE_TTL = 3600  # 1 hour

# In-memory TTL cache for source availability results.
_source_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=1000, ttl=CACHE_TTL)


def _cache_key(url: str) -> str:
    """Deterministic cache key from URL."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"source_check:{url_hash}"


async def _get_cached(url: str) -> dict[str, Any] | None:
    """Retrieve cached availability result."""
    try:
        return _source_cache.get(_cache_key(url))
    except Exception:
        logger.debug("Cache get failed for source check: %s", url, exc_info=True)
    return None


async def _set_cached(url: str, result: dict[str, Any]) -> None:
    """Store availability result in cache."""
    try:
        _source_cache[_cache_key(url)] = result
    except Exception:
        logger.debug("Cache set failed for source check: %s", url, exc_info=True)


# ── Rate limiter (shared across all source checks) ──────────────────────────

_rate_limiter = TokenBucketRateLimiter(rate=0.5, burst=2)

# Maximum concurrent checks
_semaphore = asyncio.Semaphore(3)

# Request timeout
_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


# ── Main check function ──────────────────────────────────────────────────────


async def check_source_availability(url: str) -> dict[str, Any]:
    """Check URL accessibility via HEAD request.

    Returns dict with keys: url, status, checked_at, detail, final_url.
    Results are cached for 1 hour. Rate limited to 0.5 req/s with burst of 2.
    """
    now = datetime.now(UTC).isoformat()

    # Check cache first
    cached = await _get_cached(url)
    if cached is not None:
        return cached

    # Rate limit
    await _rate_limiter.acquire()

    result: dict[str, Any] = {
        "url": url,
        "status": "unknown",
        "checked_at": now,
        "detail": "Unable to verify — request could not be completed.",
        "final_url": url,
    }

    async with _semaphore:
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT,
                follow_redirects=False,
                headers={
                    "User-Agent": "OSINT-Nexus/0.1 (Source Availability Check)",
                    "Accept": "*/*",
                },
            ) as client:
                response = await client.head(url)

                status = map_http_status(response.status_code)
                result["status"] = status
                result["final_url"] = str(response.url)

                # Build human-readable detail
                if status == "available":
                    result["detail"] = "Source is accessible."
                elif status == "not_found":
                    result["detail"] = (
                        "Not found — the source returned HTTP 404 during verification."
                    )
                elif status == "redirected":
                    result["detail"] = (
                        f"Redirected — the source redirects to {result['final_url']}."
                    )
                elif status == "access_denied":
                    result["detail"] = "Access restricted — the source returned HTTP 403."
                elif status == "auth_required":
                    result["detail"] = "Authentication required — the source requires login."
                elif status == "rate_limited":
                    result["detail"] = "Rate limited — the source returned HTTP 429."
                elif status == "temporarily_unavailable":
                    result["detail"] = (
                        "Temporarily unavailable — the source returned a server error."
                    )
                else:
                    result["detail"] = (
                        f"Unable to verify — source returned HTTP {response.status_code}."
                    )

        except httpx.TimeoutException:
            result["status"] = "unknown"
            result["detail"] = "Unable to verify — the request timed out."
        except httpx.ConnectError:
            result["status"] = "unknown"
            result["detail"] = "Unable to verify — could not connect to the source."
        except Exception as exc:
            logger.debug("Source availability check failed for %s: %s", url, exc)
            result["status"] = "unknown"
            result["detail"] = "Unable to verify — an unexpected error occurred during checking."

    # Cache the result
    await _set_cached(url, result)

    return result
