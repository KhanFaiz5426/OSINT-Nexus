"""HackerNews collector — Query HN's public API for user profiles.

Uses HackerNews's Firebase-based public API (no auth required).
Provides user karma, creation date, and submission history.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.collectors.base import OSINTCollector
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsCollector(OSINTCollector):
    """HackerNews public API collector for user profiles."""

    name = "hackernews"
    version = "1.0.0"
    supported_target_types = [TargetType.USERNAME]
    requires_api_key = False
    cache_ttl = 3600
    rate_limit_rpm = 30

    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        url = f"{HN_API_BASE}/user/{target}.json"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url)

                if response.status_code == 404 or response.text == "null":
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"hn:user:{target}",
                        status=ObservationStatus.SUCCESS,
                        raw_response={"username": target, "found": False},
                        normalized_value=target,
                        confidence=0.2,
                        metadata={"message": "HackerNews user not found"},
                    )

                if response.status_code != 200:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"hn:user:{target}",
                        status=ObservationStatus.ERROR,
                        error_message=f"HN API returned HTTP {response.status_code}",
                    )

                data = response.json()
                if data is None:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"hn:user:{target}",
                        status=ObservationStatus.SUCCESS,
                        raw_response={"username": target, "found": False},
                        normalized_value=target,
                        confidence=0.2,
                        metadata={"message": "HackerNews user not found"},
                    )

                profile = {
                    "username": data.get("id", ""),
                    "karma": data.get("karma", 0),
                    "created": data.get("created", 0),
                    "about": data.get("about", ""),
                    "submitted_count": len(data.get("submitted", [])),
                    "profile_url": f"https://news.ycombinator.com/user?id={target}",
                }

                return RawResult(
                    collector_name=self.name,
                    collector_version=self.version,
                    target=target,
                    target_type=target_type,
                    query=f"hn:user:{target}",
                    status=ObservationStatus.SUCCESS,
                    raw_response={"profile": profile, "found": True},
                    normalized_value=target,
                    confidence=0.9,
                    metadata={
                        "karma": profile["karma"],
                        "submitted_count": profile["submitted_count"],
                    },
                )

        except httpx.TimeoutException:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"hn:user:{target}",
                status=ObservationStatus.TIMEOUT,
                error_message="HN API request timed out",
            )
        except Exception as exc:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"hn:user:{target}",
                status=ObservationStatus.ERROR,
                error_message=f"HN collection failed: {exc}",
            )
