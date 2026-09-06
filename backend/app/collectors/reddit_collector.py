"""Reddit collector — Query Reddit's public JSON API for user profiles.

Uses Reddit's public .json endpoints (no auth required).
Rate limited to 10 req/min to respect Reddit's guidelines.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.collectors.base import OSINTCollector
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)

REDDIT_API_BASE = "https://www.reddit.com"
USER_AGENT = "OSINT-Nexus/1.0 (research; +https://github.com/osint-nexus)"


class RedditCollector(OSINTCollector):
    """Reddit public JSON API collector for user profiles."""

    name = "reddit"
    version = "1.0.0"
    supported_target_types = [TargetType.USERNAME]
    requires_api_key = False
    cache_ttl = 3600
    rate_limit_rpm = 10

    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        url = f"{REDDIT_API_BASE}/user/{target}/about.json"
        headers = {"User-Agent": USER_AGENT}

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 404:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"reddit:user:{target}",
                        status=ObservationStatus.SUCCESS,
                        raw_response={"username": target, "found": False},
                        normalized_value=target,
                        confidence=0.2,
                        metadata={"message": "Reddit user not found"},
                    )

                if response.status_code == 429:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"reddit:user:{target}",
                        status=ObservationStatus.ERROR,
                        error_message="Reddit rate limit exceeded",
                    )

                if response.status_code != 200:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"reddit:user:{target}",
                        status=ObservationStatus.ERROR,
                        error_message=f"Reddit API returned HTTP {response.status_code}",
                    )

                data = response.json()
                user_data = data.get("data", {})

                profile = {
                    "name": user_data.get("name", ""),
                    "icon_img": user_data.get("icon_img", ""),
                    "banner_img": user_data.get("banner_img", ""),
                    "description": user_data.get("subreddit", {}).get("public_description", "")
                    if isinstance(user_data.get("subreddit"), dict)
                    else "",
                    "link_karma": user_data.get("link_karma", 0),
                    "comment_karma": user_data.get("comment_karma", 0),
                    "total_karma": user_data.get("total_karma", 0),
                    "created_utc": user_data.get("created_utc", 0),
                    "verified": user_data.get("verified", False),
                    "has_verified_email": user_data.get("has_verified_email", False),
                    "is_gold": user_data.get("is_gold", False),
                    "is_mod": user_data.get("is_mod", False),
                    "over_18": user_data.get("over_18", False),
                    "profile_url": f"https://www.reddit.com/user/{target}",
                }

                return RawResult(
                    collector_name=self.name,
                    collector_version=self.version,
                    target=target,
                    target_type=target_type,
                    query=f"reddit:user:{target}",
                    status=ObservationStatus.SUCCESS,
                    raw_response={"profile": profile, "found": True},
                    normalized_value=target,
                    confidence=0.9,
                    metadata={
                        "link_karma": profile["link_karma"],
                        "comment_karma": profile["comment_karma"],
                        "has_verified_email": profile["has_verified_email"],
                    },
                )

        except httpx.TimeoutException:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"reddit:user:{target}",
                status=ObservationStatus.TIMEOUT,
                error_message="Reddit API request timed out",
            )
        except Exception as exc:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"reddit:user:{target}",
                status=ObservationStatus.ERROR,
                error_message=f"Reddit collection failed: {exc}",
            )
