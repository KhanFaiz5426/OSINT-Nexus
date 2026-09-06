"""GitLab collector — Query GitLab's public API for user profiles.

Uses GitLab's public v4 API (no auth required for public users).
Provides profile data, projects, and groups.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.collectors.base import OSINTCollector
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)

GITLAB_API_BASE = "https://gitlab.com/api/v4"


class GitLabCollector(OSINTCollector):
    """GitLab public API collector for user profiles and projects."""

    name = "gitlab"
    version = "1.0.0"
    supported_target_types = [TargetType.USERNAME]
    requires_api_key = False
    cache_ttl = 3600
    rate_limit_rpm = 20

    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        headers = {"User-Agent": "OSINT-Nexus/1.0 (research)"}

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                # Search for user by username
                search_url = f"{GITLAB_API_BASE}/users"
                search_response = await client.get(
                    search_url, headers=headers, params={"username": target, "per_page": 5}
                )

                if search_response.status_code != 200:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"gitlab:user:{target}",
                        status=ObservationStatus.ERROR,
                        error_message=f"GitLab search returned HTTP {search_response.status_code}",
                    )

                users = search_response.json()
                if not users:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"gitlab:user:{target}",
                        status=ObservationStatus.SUCCESS,
                        raw_response={"username": target, "found": False},
                        normalized_value=target,
                        confidence=0.2,
                        metadata={"message": "GitLab user not found"},
                    )

                # Find exact match
                user = None
                for u in users:
                    if u.get("username", "").lower() == target.lower():
                        user = u
                        break
                if user is None:
                    user = users[0]

                # Fetch user's projects
                projects_url = f"{GITLAB_API_BASE}/users/{user['id']}/projects"
                projects_response = await client.get(
                    projects_url, headers=headers, params={"per_page": 20, "order_by": "last_activity_at"}
                )
                projects = projects_response.json() if projects_response.status_code == 200 else []

                # Fetch user's groups
                groups_url = f"{GITLAB_API_BASE}/users/{user['id']}/groups"
                groups_response = await client.get(
                    groups_url, headers=headers, params={"per_page": 20}
                )
                groups = groups_response.json() if groups_response.status_code == 200 else []

                profile = {
                    "username": user.get("username", ""),
                    "name": user.get("name", ""),
                    "email": user.get("public_email", ""),
                    "bio": user.get("bio", ""),
                    "location": user.get("location", ""),
                    "website_url": user.get("website_url", ""),
                    "organization": user.get("organization", ""),
                    "avatar_url": user.get("avatar_url", ""),
                    "created_at": user.get("created_at", ""),
                    "last_activity_on": user.get("last_activity_on", ""),
                    "state": user.get("state", ""),
                    "projects_count": user.get("projects_count", 0),
                    "identities": user.get("identities", []),
                    "profile_url": user.get("web_url", f"https://gitlab.com/{target}"),
                }

                project_list = [
                    {
                        "name": p.get("name", ""),
                        "path": p.get("path_with_namespace", ""),
                        "description": p.get("description", ""),
                        "url": p.get("web_url", ""),
                        "star_count": p.get("star_count", 0),
                        "forks_count": p.get("forks_count", 0),
                        "language": p.get("language", ""),
                        "created_at": p.get("created_at", ""),
                        "last_activity_at": p.get("last_activity_at", ""),
                    }
                    for p in projects[:20]
                ]

                group_list = [
                    {
                        "name": g.get("name", ""),
                        "path": g.get("full_path", ""),
                        "description": g.get("description", ""),
                        "url": g.get("web_url", ""),
                        "visibility": g.get("visibility", ""),
                    }
                    for g in groups[:20]
                ]

                return RawResult(
                    collector_name=self.name,
                    collector_version=self.version,
                    target=target,
                    target_type=target_type,
                    query=f"gitlab:user:{target}",
                    status=ObservationStatus.SUCCESS,
                    raw_response={
                        "profile": profile,
                        "projects": project_list,
                        "groups": group_list,
                        "found": True,
                    },
                    normalized_value=target,
                    confidence=0.9,
                    metadata={
                        "project_count": len(project_list),
                        "group_count": len(group_list),
                        "has_email": bool(profile["email"]),
                        "has_org": bool(profile["organization"]),
                    },
                )

        except httpx.TimeoutException:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"gitlab:user:{target}",
                status=ObservationStatus.TIMEOUT,
                error_message="GitLab API request timed out",
            )
        except Exception as exc:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"gitlab:user:{target}",
                status=ObservationStatus.ERROR,
                error_message=f"GitLab collection failed: {exc}",
            )
