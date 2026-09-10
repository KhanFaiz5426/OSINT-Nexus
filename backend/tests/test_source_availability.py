"""Tests for the source availability service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.source_availability import (
    _cache_key,
    check_source_availability,
    map_http_status,
)


class TestMapHttpStatus:
    """Test HTTP status to availability state mapping."""

    def test_200_is_available(self):
        assert map_http_status(200) == "available"

    def test_201_is_available(self):
        assert map_http_status(201) == "available"

    def test_204_is_available(self):
        assert map_http_status(204) == "available"

    def test_301_is_redirected(self):
        assert map_http_status(301) == "redirected"

    def test_302_is_redirected(self):
        assert map_http_status(302) == "redirected"

    def test_307_is_redirected(self):
        assert map_http_status(307) == "redirected"

    def test_308_is_redirected(self):
        assert map_http_status(308) == "redirected"

    def test_403_is_access_denied(self):
        assert map_http_status(403) == "access_denied"

    def test_404_is_not_found(self):
        assert map_http_status(404) == "not_found"

    def test_401_is_auth_required(self):
        assert map_http_status(401) == "auth_required"

    def test_429_is_rate_limited(self):
        assert map_http_status(429) == "rate_limited"

    def test_500_is_temporarily_unavailable(self):
        assert map_http_status(500) == "temporarily_unavailable"

    def test_502_is_temporarily_unavailable(self):
        assert map_http_status(502) == "temporarily_unavailable"

    def test_503_is_temporarily_unavailable(self):
        assert map_http_status(503) == "temporarily_unavailable"

    def test_unknown_status(self):
        assert map_http_status(418) == "unknown"


class TestCacheKey:
    """Test cache key generation."""

    def test_deterministic(self):
        key1 = _cache_key("https://example.com")
        key2 = _cache_key("https://example.com")
        assert key1 == key2

    def test_different_urls_different_keys(self):
        key1 = _cache_key("https://example.com")
        key2 = _cache_key("https://other.com")
        assert key1 != key2

    def test_prefix(self):
        key = _cache_key("https://example.com")
        assert key.startswith("osint:source_check:")


class TestCheckSourceAvailability:
    """Test the main availability check function."""

    @pytest.mark.asyncio
    async def test_returns_cached_result(self):
        """When cache has a result, it should be returned without making a request."""
        cached = {
            "url": "https://example.com",
            "status": "available",
            "checked_at": "2026-01-01T00:00:00Z",
            "detail": "Source is accessible.",
            "final_url": "https://example.com",
        }
        with patch(
            "app.services.source_availability._get_cached", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = cached
            result = await check_source_availability("https://example.com")
            assert result == cached
            mock_get.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_available_url(self):
        """A 200 response should map to 'available' status."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"

        mock_client = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "app.services.source_availability._get_cached",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.source_availability._set_cached", new_callable=AsyncMock),
            patch("app.services.source_availability._rate_limiter") as mock_limiter,
            patch("httpx.AsyncClient") as mock_httpx,
        ):
            mock_limiter.acquire = AsyncMock(return_value=0.0)
            mock_httpx.return_value = mock_client

            result = await check_source_availability("https://example.com")
            assert result["status"] == "available"
            assert result["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_not_found_url(self):
        """A 404 response should map to 'not_found' status."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.url = "https://example.com/deleted"

        mock_client = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "app.services.source_availability._get_cached",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.source_availability._set_cached", new_callable=AsyncMock),
            patch("app.services.source_availability._rate_limiter") as mock_limiter,
            patch("httpx.AsyncClient") as mock_httpx,
        ):
            mock_limiter.acquire = AsyncMock(return_value=0.0)
            mock_httpx.return_value = mock_client

            result = await check_source_availability("https://example.com/deleted")
            assert result["status"] == "not_found"
            assert "404" in result["detail"]

    @pytest.mark.asyncio
    async def test_access_denied(self):
        """A 403 response should map to 'access_denied'."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.url = "https://example.com/private"

        mock_client = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "app.services.source_availability._get_cached",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.source_availability._set_cached", new_callable=AsyncMock),
            patch("app.services.source_availability._rate_limiter") as mock_limiter,
            patch("httpx.AsyncClient") as mock_httpx,
        ):
            mock_limiter.acquire = AsyncMock(return_value=0.0)
            mock_httpx.return_value = mock_client

            result = await check_source_availability("https://example.com/private")
            assert result["status"] == "access_denied"
            assert "403" in result["detail"]

    @pytest.mark.asyncio
    async def test_timeout_returns_unknown(self):
        """A timeout should return 'unknown' status with appropriate detail."""
        import httpx

        mock_client = AsyncMock()
        mock_client.head.side_effect = httpx.TimeoutException("timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "app.services.source_availability._get_cached",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.source_availability._set_cached", new_callable=AsyncMock),
            patch("app.services.source_availability._rate_limiter") as mock_limiter,
            patch("httpx.AsyncClient") as mock_httpx,
        ):
            mock_limiter.acquire = AsyncMock(return_value=0.0)
            mock_httpx.return_value = mock_client

            result = await check_source_availability("https://slow.example.com")
            assert result["status"] == "unknown"
            assert "timed out" in result["detail"].lower()

    @pytest.mark.asyncio
    async def test_redirect_includes_final_url(self):
        """A 302 response should include the redirect target."""
        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.url = "https://new.example.com"

        mock_client = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "app.services.source_availability._get_cached",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.source_availability._set_cached", new_callable=AsyncMock),
            patch("app.services.source_availability._rate_limiter") as mock_limiter,
            patch("httpx.AsyncClient") as mock_httpx,
        ):
            mock_limiter.acquire = AsyncMock(return_value=0.0)
            mock_httpx.return_value = mock_client

            result = await check_source_availability("https://old.example.com")
            assert result["status"] == "redirected"
            assert result["final_url"] == "https://new.example.com"
