"""Tests for collector infrastructure: cache, rate limiter, retry, registry."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.collectors.cache import CollectorCache
from app.collectors.rate_limiter import TokenBucketRateLimiter
from app.collectors.registry import (
    get_collector,
    get_collectors_for_target,
    register_collector,
)
from app.collectors.retry import _is_retryable_error, retry_with_backoff
from app.models import ObservationStatus, RawResult, TargetType

# ── Cache Tests ──────────────────────────────────────────────────────────────


class TestCollectorCache:
    """Tests for Redis-based collector cache."""

    @pytest.mark.anyio
    async def test_cache_miss(self):
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        cache = CollectorCache(mock_redis)

        result = await cache.get("dns:example.com:domain")
        assert result is None

    @pytest.mark.anyio
    async def test_cache_hit(self):
        mock_redis = AsyncMock()
        raw_result = RawResult(
            collector_name="dns",
            collector_version="1.0.0",
            target="example.com",
            target_type=TargetType.DOMAIN,
            status=ObservationStatus.SUCCESS,
            raw_response={"A": [{"type": "A", "value": "1.2.3.4"}]},
            normalized_value="1.2.3.4",
            confidence=0.95,
        )
        mock_redis.get = AsyncMock(return_value=raw_result.model_dump_json())

        cache = CollectorCache(mock_redis)
        result = await cache.get("dns:example.com:domain")

        assert result is not None
        assert result.target == "example.com"
        assert result.confidence == 0.95

    @pytest.mark.anyio
    async def test_cache_set(self):
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        cache = CollectorCache(mock_redis)

        raw_result = RawResult(
            collector_name="dns",
            target="example.com",
            target_type=TargetType.DOMAIN,
        )
        await cache.set("dns:example.com:domain", raw_result, ttl=3600)

        mock_redis.set.assert_called_once()

    @pytest.mark.anyio
    async def test_cache_invalidate(self):
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)
        cache = CollectorCache(mock_redis)

        result = await cache.invalidate("dns:example.com:domain")
        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.anyio
    async def test_cache_clear_collector(self):
        mock_redis = AsyncMock()

        async def mock_scan_iter(match):
            yield "osint:cache:dns:a.com:domain"
            yield "osint:cache:dns:b.com:domain"

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete = AsyncMock()
        cache = CollectorCache(mock_redis)

        count = await cache.clear_collector("dns")
        assert count == 2


# ── Rate Limiter Tests ──────────────────────────────────────────────────────


class TestTokenBucketRateLimiter:
    """Tests for token bucket rate limiter."""

    @pytest.mark.anyio
    async def test_acquire_single_token(self):
        limiter = TokenBucketRateLimiter(rate=10.0, burst=10)
        waited = await limiter.acquire(1)
        assert waited == 0.0
        assert limiter.available_tokens <= 10

    @pytest.mark.anyio
    async def test_acquire_respects_burst(self):
        limiter = TokenBucketRateLimiter(rate=1.0, burst=5)
        # Consume all burst tokens
        for _ in range(5):
            await limiter.acquire(1)
        # Next acquire should wait
        waited = await limiter.acquire(1)
        assert waited > 0.0

    @pytest.mark.anyio
    async def test_concurrent_acquire(self):
        limiter = TokenBucketRateLimiter(rate=100.0, burst=10)
        results = await asyncio.gather(*[limiter.acquire(1) for _ in range(10)])
        assert all(isinstance(r, float) for r in results)


# ── Retry Tests ──────────────────────────────────────────────────────────────


class TestRetryLogic:
    """Tests for exponential backoff retry."""

    @pytest.mark.anyio
    async def test_succeeds_first_attempt(self):
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await retry_with_backoff(success_func, max_attempts=3, base_delay=0.01)
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.anyio
    async def test_retries_on_transient_error(self):
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("connection reset")
            return "ok"

        result = await retry_with_backoff(
            fail_then_succeed, max_attempts=3, base_delay=0.01
        )
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.anyio
    async def test_raises_after_max_attempts(self):
        async def always_fail():
            raise ConnectionError("connection reset")

        with pytest.raises(ConnectionError):
            await retry_with_backoff(always_fail, max_attempts=2, base_delay=0.01)

    @pytest.mark.anyio
    async def test_does_not_retry_non_retryable(self):
        call_count = 0

        async def value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("not transient")

        with pytest.raises(ValueError):
            await retry_with_backoff(value_error, max_attempts=3, base_delay=0.01)
        assert call_count == 1

    def test_is_retryable_connection_error(self):
        assert _is_retryable_error(ConnectionError("reset")) is True

    def test_is_retryable_timeout(self):
        assert _is_retryable_error(TimeoutError("timed out")) is True

    def test_is_retryable_value_error(self):
        assert _is_retryable_error(ValueError("bad value")) is False


# ── Registry Tests ───────────────────────────────────────────────────────────


class TestCollectorRegistry:
    """Tests for collector registration and discovery."""

    def setup_method(self):
        """Clear registry before each test."""
        from app.collectors.registry import _collectors
        _collectors.clear()

    def test_register_and_get_collector(self):
        from app.collectors.base import OSINTCollector

        class MockCollector(OSINTCollector):
            name = "test_mock"
            version = "0.0.1"
            supported_target_types = [TargetType.DOMAIN]

            async def _collect(self, target, target_type):
                pass

        collector = MockCollector()
        register_collector(collector)

        assert get_collector("test_mock") is collector

    def test_get_collectors_for_target(self):
        from app.collectors.base import OSINTCollector

        class DomainCollector(OSINTCollector):
            name = "test_domain"
            version = "0.0.1"
            supported_target_types = [TargetType.DOMAIN]

            async def _collect(self, target, target_type):
                pass

        class IPOollector(OSINTCollector):
            name = "test_ip"
            version = "0.0.1"
            supported_target_types = [TargetType.IP]

            async def _collect(self, target, target_type):
                pass

        register_collector(DomainCollector())
        register_collector(IPOollector())

        domain_collectors = get_collectors_for_target(TargetType.DOMAIN)
        assert len(domain_collectors) == 1
        assert domain_collectors[0].name == "test_domain"

        ip_collectors = get_collectors_for_target(TargetType.IP)
        assert len(ip_collectors) == 1
        assert ip_collectors[0].name == "test_ip"
