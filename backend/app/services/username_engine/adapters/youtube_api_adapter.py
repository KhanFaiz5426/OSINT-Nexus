"""YouTube API adapter — uses YouTube Data API v3 for username discovery.

YouTube Data API v3 provides a legitimate, public-API path for discovering
channel presence. The ``channels.list`` endpoint supports:
- ``forHandle``: the @username handle (e.g. ``@geerlingguy``)
- ``forUsername``: legacy username (less reliable)

This adapter requires a YOUTUBE_API_KEY environment variable.
Without it, the adapter reports unavailable and the orchestrator
falls back to search-discovery.

API docs: https://developers.google.com/youtube/v3/docs/channels/list
"""

from __future__ import annotations

import logging

import httpx

from app.services.username_engine.adapters.base import (
    AcquisitionMethod,
    AdapterResult,
    EvidenceConfidence,
    PlatformAdapter,
)

logger = logging.getLogger(__name__)

_YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
_YOUTUBE_CHANNEL_URL = "https://www.youtube.com/@{username}"


def _get_youtube_api_key() -> str:
    """Load YouTube API key from settings."""
    try:
        from app.core.config import get_settings

        settings = get_settings()
        return getattr(settings, "YOUTUBE_API_KEY", "")
    except Exception:
        return ""


class YouTubeAPIAdapter(PlatformAdapter):
    """Adapter that discovers YouTube channels via the Data API v3.

    Uses channels.list with forHandle to check if a @username channel exists.
    Returns structured profile data (title, subscriber count, description)
    when found.

    Falls back gracefully: if no API key is configured, returns
    ``is_available = False`` and the orchestrator skips this adapter.
    """

    @property
    def name(self) -> str:
        return "youtube_api"

    @property
    def acquisition_method(self) -> AcquisitionMethod:
        return AcquisitionMethod.API

    @property
    def supported_platforms(self) -> list[str]:
        return ["youtube"]

    @property
    def is_available(self) -> bool:
        return bool(_get_youtube_api_key())

    async def probe(
        self,
        platform_key: str,
        username: str,
        investigation_id: str,
    ) -> AdapterResult | None:
        """Probe YouTube via Data API v3 channels.list.

        Tries forHandle first (the @username convention), then falls back
        to forUsername for legacy channels.
        """
        if platform_key not in self.supported_platforms:
            return None

        api_key = _get_youtube_api_key()
        if not api_key:
            return AdapterResult(
                platform_key="youtube",
                platform_name="YouTube",
                username=username,
                found=False,
                url=_YOUTUBE_CHANNEL_URL.format(username=username),
                acquisition_method=self.acquisition_method,
                error="YOUTUBE_API_KEY not configured",
                evidence_confidence=EvidenceConfidence.HIGH,
            )

        url = _YOUTUBE_CHANNEL_URL.format(username=username)

        # Try forHandle first (@username)
        result = await self._try_handle(api_key, username, url)
        if result is not None:
            return result

        # Fall back to forUsername (legacy)
        result = await self._try_username(api_key, username, url)
        if result is not None:
            return result

        # Neither worked — username not found
        return AdapterResult(
            platform_key="youtube",
            platform_name="YouTube",
            username=username,
            found=False,
            url=url,
            acquisition_method=self.acquisition_method,
            status_code=200,
            evidence_confidence=EvidenceConfidence.HIGH,
            evidence={"api_method": "channels.list", "query_type": "not_found"},
        )

    async def _try_handle(self, api_key: str, username: str, url: str) -> AdapterResult | None:
        """Try channels.list with forHandle (@username)."""
        handle = username if username.startswith("@") else f"@{username}"
        return await self._query_channels(api_key, username, url, {"forHandle": handle})

    async def _try_username(self, api_key: str, username: str, url: str) -> AdapterResult | None:
        """Try channels.list with forUsername (legacy)."""
        return await self._query_channels(api_key, username, url, {"forUsername": username})

    async def _query_channels(
        self,
        api_key: str,
        username: str,
        url: str,
        params: dict[str, str],
    ) -> AdapterResult | None:
        """Execute channels.list and parse the response."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{_YOUTUBE_API_BASE}/channels",
                    params={
                        "part": "snippet,statistics,contentDetails",
                        "key": api_key,
                        **params,
                    },
                )

                if response.status_code != 200:
                    logger.debug(
                        "YouTube API returned %d: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    return None

                data = response.json()
                items = data.get("items", [])

                if not items:
                    return None

                channel = items[0]
                snippet = channel.get("snippet", {})
                statistics = channel.get("statistics", {})
                channel.get("contentDetails", {})

                # Build profile
                profile = {
                    "platform": "YouTube",
                    "channel_id": channel.get("id", ""),
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", "")[:500],
                    "custom_url": snippet.get("customUrl", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                    "country": snippet.get("country", ""),
                    "view_count": statistics.get("viewCount", "0"),
                    "subscriber_count": statistics.get("subscriberCount", "0"),
                    "video_count": statistics.get("videoCount", "0"),
                    "url": url,
                }

                # Compute confidence based on channel completeness
                confidence = 0.9  # API-verified is high confidence
                if statistics.get("subscriberCount", "0") != "0":
                    confidence = 0.95
                if snippet.get("description"):
                    confidence = min(confidence + 0.02, 0.98)

                return AdapterResult(
                    platform_key="youtube",
                    platform_name="YouTube",
                    username=username,
                    found=True,
                    url=url,
                    acquisition_method=self.acquisition_method,
                    status_code=200,
                    confidence=confidence,
                    evidence_confidence=EvidenceConfidence.HIGH,
                    evidence={
                        "api_method": "channels.list",
                        "query_type": list(params.keys())[0],
                        "channel_id": channel.get("id", ""),
                        "subscriber_count": statistics.get("subscriberCount", "0"),
                        "video_count": statistics.get("videoCount", "0"),
                    },
                    profile=profile,
                )

        except httpx.TimeoutException:
            logger.debug("YouTube API timeout for %s", username)
            return None
        except httpx.RequestError as exc:
            logger.debug("YouTube API request error for %s: %s", username, exc)
            return None
        except Exception as exc:
            logger.debug("YouTube API parse error for %s: %s", username, exc)
            return None
