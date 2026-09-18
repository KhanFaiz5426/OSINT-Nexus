"""Collector base — OSINTCollector protocol and base class.

All collectors implement the OSINTCollector protocol defined in TECH_STACK.md.
The BaseCollector abstract class provides shared infrastructure: caching, rate
limiting, retry logic, and error handling.
"""

from __future__ import annotations

import abc
import logging
import time
from typing import Any

from app.collectors.cache import CollectorCache
from app.collectors.rate_limiter import TokenBucketRateLimiter
from app.collectors.retry import retry_with_backoff
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)


def _resolve_cache_ttl(collector_name: str, class_default: int) -> int:
    """Return the cache TTL, preferring the global runtime settings store
    over the collector class default.
    """
    try:
        from app.core.settings_store import SETTINGS_FILE, get_app_settings

        if not SETTINGS_FILE.exists():
            return class_default
        settings = get_app_settings()
        # Ensure it reads cache_ttl instead of rate_limits.
        return settings.collectors.cache_ttl
    except Exception:
        return class_default


def _resolve_rate_limit_rpm(collector_name: str, class_default: int) -> int:
    """Return the rate limit RPM for *collector_name*, preferring per-collector
    overrides from the runtime settings store over the collector class default.

    Only returns a non-default value when the settings file explicitly
    contains a per-collector entry for *collector_name* in ``rate_limits``.
    """
    try:
        from app.core.settings_store import SETTINGS_FILE, get_app_settings

        if not SETTINGS_FILE.exists():
            return class_default
        settings = get_app_settings()
        
        # Search rate limit is explicitly exposed in the UI as search_rate_limit_rpm
        if collector_name == "search":
            return settings.collectors.search_rate_limit_rpm
            
        return settings.collectors.rate_limits.get(collector_name, class_default)
    except Exception:
        return class_default


class OSINTCollector(abc.ABC):
    """Abstract base class for all OSINT collectors.

    Every concrete collector must implement:
      - name: unique identifier
      - version: semantic version string
      - supported_target_types: which TargetType values this collector handles
      - requires_api_key: whether the collector needs an external API key
      - cache_ttl: seconds to cache results (0 = no caching)
      - rate_limit_rpm: max requests per minute (0 = unlimited)
      - _collect(): the actual collection logic

    Cache TTL and rate limits are resolved at init time from the runtime
    settings store (``collectors.cache_ttl``, ``collectors.rate_limits``).
    If the store is unavailable the collector class defaults are used.
    """

    name: str = "base"
    version: str = "1.0.0"
    supported_target_types: list[TargetType] = []
    requires_api_key: bool = False
    cache_ttl: int = 86400  # 24 hours default
    rate_limit_rpm: int = 0  # 0 = unlimited

    def __init__(self, cache: CollectorCache | None = None) -> None:
        self._cache = cache
        # Resolve effective cache TTL and rate limit from settings store.
        self.cache_ttl = _resolve_cache_ttl(self.name, self.cache_ttl)
        self.rate_limit_rpm = _resolve_rate_limit_rpm(self.name, self.rate_limit_rpm)
        self._rate_limiter: TokenBucketRateLimiter | None = None
        if self.rate_limit_rpm > 0:
            self._rate_limiter = TokenBucketRateLimiter(
                rate=self.rate_limit_rpm / 60.0,  # convert RPM to req/sec
                burst=self.rate_limit_rpm,
            )

    async def collect(
        self,
        target: str,
        target_type: TargetType,
        *,
        force_refresh: bool = False,
    ) -> RawResult:
        """Execute collection with caching, rate limiting, and retry.

        This is the public entry point. Do not override in subclasses.
        """
        # Check target type support
        if target_type not in self.supported_target_types:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                status=ObservationStatus.ERROR,
                error_message=f"Unsupported target type: {target_type}",
            )

        # Check API key availability
        if self.requires_api_key and not self._is_api_key_available():
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                status=ObservationStatus.ERROR,
                error_message=f"API key not configured for {self.name}",
            )

        # Check cache
        cache_key = f"{self.name}:{target}:{target_type.value}"
        if not force_refresh and self._cache and self.cache_ttl > 0:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for %s", cache_key)
                return cached

        # Rate limiting
        if self._rate_limiter:
            await self._rate_limiter.acquire()

        # Execute with retry
        try:
            result = await retry_with_backoff(
                self._collect,
                target=target,
                target_type=target_type,
                max_attempts=3,
                base_delay=1.0,
                max_delay=8.0,
            )
        except TimeoutError:
            result = RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                status=ObservationStatus.TIMEOUT,
                error_message="Collection timed out after retries",
            )
        except Exception as exc:
            logger.exception("Collector %s failed for %s", self.name, target)
            result = RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                status=ObservationStatus.ERROR,
                error_message=str(exc),
            )

        # Store in cache on success
        if result.status == ObservationStatus.SUCCESS and self._cache and self.cache_ttl > 0:
            await self._cache.set(cache_key, result, ttl=self.cache_ttl)

        return result

    @abc.abstractmethod
    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        """Perform the actual collection. Must be implemented by subclasses.

        Should raise exceptions on transient failures (retry will handle them).
        Return a RawResult with status=ERROR for permanent failures.
        """

    def _is_api_key_available(self) -> bool:
        """Override to check if the required API key is configured."""
        return False

    async def health_check(self) -> dict[str, Any]:
        """Return collector health information."""
        return {
            "name": self.name,
            "version": self.version,
            "available": True,
            "api_key_configured": (not self.requires_api_key or self._is_api_key_available()),
            "rate_limit_rpm": self.rate_limit_rpm,
            "cache_ttl_seconds": self.cache_ttl,
        }

    def _now_iso(self) -> str:
        """Return current UTC time as ISO 8601 string."""
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
