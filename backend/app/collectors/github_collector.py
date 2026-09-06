"""GitHub collector — Query GitHub API for user profiles and repositories.

For username investigations: profile data, repositories, organization membership.
Uses the GitHub REST API (v3). Works without authentication (60 req/hour)
or with a token (5000 req/hour).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.collectors.base import OSINTCollector
from app.core.config import get_settings
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubCollector(OSINTCollector):
    """GitHub API collector for user profiles and repositories."""

    name = "github"
    version = "1.0.0"
    supported_target_types = [TargetType.USERNAME, TargetType.EMAIL]
    requires_api_key = False  # Works without token, but rate limited
    cache_ttl = 3600  # 1 hour
    rate_limit_rpm = 30  # Conservative: 30 req/min

    def _is_api_key_available(self) -> bool:
        settings = get_settings()
        return bool(settings.GITHUB_TOKEN)

    def _get_headers(self) -> dict[str, str]:
        settings = get_settings()
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "OSINT-Nexus/1.0 (research)",
        }
        if settings.GITHUB_TOKEN:
            headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"
        return headers

    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        settings = get_settings()

        # For email targets, search GitHub by email first
        if target_type == TargetType.EMAIL:
            return await self._collect_by_email(target, target_type, settings)

        # For username targets, fetch profile directly
        return await self._collect_by_username(target, target_type, settings)

    async def _collect_by_email(
        self, target: str, target_type: TargetType, settings: Any
    ) -> RawResult:
        """Search GitHub for users associated with an email address."""
        url = f"{GITHUB_API_BASE}/search/users"
        params = {"q": f"{target} in:email", "per_page": 10}

        try:
            async with httpx.AsyncClient(timeout=settings.GITHUB_TIMEOUT) as client:
                response = await client.get(url, headers=self._get_headers(), params=params)

                if response.status_code == 403:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"github:search:email:{target}",
                        status=ObservationStatus.ERROR,
                        error_message="GitHub API rate limit exceeded",
                    )
                if response.status_code != 200:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"github:search:email:{target}",
                        status=ObservationStatus.ERROR,
                        error_message=f"GitHub search returned HTTP {response.status_code}",
                    )

                data = response.json()
                users = data.get("items", [])

                if not users:
                    return RawResult(
                        collector_name=self.name,
                        collector_version=self.version,
                        target=target,
                        target_type=target_type,
                        query=f"github:search:email:{target}",
                        status=ObservationStatus.SUCCESS,
                        raw_response={"email": target, "users": [], "profile": None},
                        normalized_value=target,
                        confidence=0.3,
                        metadata={"message": "No GitHub users found for this email"},
                    )

                # Fetch full profile for the first matching user
                username = users[0].get("login", "")
                profile = await self._fetch_profile(username, settings.GITHUB_TIMEOUT)
                repos = await self._fetch_repos(username, settings.GITHUB_TIMEOUT)
                orgs = await self._fetch_orgs(username, settings.GITHUB_TIMEOUT)

                raw_response = {
                    "email": target,
                    "search_results": [
                        {"login": u.get("login", ""), "id": u.get("id", 0)}
                        for u in users
                    ],
                    "profile": {
                        "login": profile.get("login", ""),
                        "name": profile.get("name", ""),
                        "email": profile.get("email", ""),
                        "bio": profile.get("bio", ""),
                        "company": profile.get("company", ""),
                        "location": profile.get("location", ""),
                        "blog": profile.get("blog", ""),
                        "public_repos": profile.get("public_repos", 0),
                        "followers": profile.get("followers", 0),
                        "following": profile.get("following", 0),
                        "created_at": profile.get("created_at", ""),
                        "updated_at": profile.get("updated_at", ""),
                        "avatar_url": profile.get("avatar_url", ""),
                    },
                    "repositories": repos,
                    "organizations": orgs,
                }

                return RawResult(
                    collector_name=self.name,
                    collector_version=self.version,
                    target=target,
                    target_type=target_type,
                    query=f"github:search:email:{target}",
                    status=ObservationStatus.SUCCESS,
                    raw_response=raw_response,
                    normalized_value=target,
                    confidence=0.85,
                    metadata={
                        "repo_count": len(repos),
                        "org_count": len(orgs),
                        "search_result_count": len(users),
                        "matched_username": username,
                    },
                )

        except httpx.TimeoutException:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"github:search:email:{target}",
                status=ObservationStatus.TIMEOUT,
                error_message=f"GitHub search timed out after {settings.GITHUB_TIMEOUT}s",
            )
        except Exception as exc:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"github:search:email:{target}",
                status=ObservationStatus.ERROR,
                error_message=f"GitHub email search failed: {exc}",
            )

    async def _collect_by_username(
        self, target: str, target_type: TargetType, settings: Any
    ) -> RawResult:
        """Fetch GitHub profile for a username."""
        profile = await self._fetch_profile(target, settings.GITHUB_TIMEOUT)
        if profile.get("error"):
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"github:user:{target}",
                status=ObservationStatus.ERROR,
                error_message=profile["error"],
            )

        # Fetch repositories
        repos = await self._fetch_repos(target, settings.GITHUB_TIMEOUT)

        # Fetch organization membership
        orgs = await self._fetch_orgs(target, settings.GITHUB_TIMEOUT)

        # Build normalized value from profile
        email = profile.get("email", "")
        name = profile.get("name", "")
        normalized = email or name or target

        raw_response = {
            "found": True,
            "profile": {
                "login": profile.get("login", ""),
                "name": profile.get("name", ""),
                "email": profile.get("email", ""),
                "bio": profile.get("bio", ""),
                "company": profile.get("company", ""),
                "location": profile.get("location", ""),
                "blog": profile.get("blog", ""),
                "public_repos": profile.get("public_repos", 0),
                "followers": profile.get("followers", 0),
                "following": profile.get("following", 0),
                "created_at": profile.get("created_at", ""),
                "updated_at": profile.get("updated_at", ""),
                "avatar_url": profile.get("avatar_url", ""),
            },
            "repositories": repos,
            "organizations": orgs,
        }

        return RawResult(
            collector_name=self.name,
            collector_version=self.version,
            target=target,
            target_type=target_type,
            query=f"github:user:{target}",
            status=ObservationStatus.SUCCESS,
            raw_response=raw_response,
            normalized_value=normalized,
            confidence=0.95,
            metadata={
                "repo_count": len(repos),
                "org_count": len(orgs),
                "has_email": bool(email),
            },
        )

    async def _fetch_profile(self, username: str, timeout: int) -> dict[str, Any]:
        """Fetch GitHub user profile."""
        url = f"{GITHUB_API_BASE}/users/{username}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, headers=self._get_headers())

                if response.status_code == 404:
                    return {"error": f"GitHub user '{username}' not found"}
                if response.status_code == 403:
                    return {"error": "GitHub API rate limit exceeded"}
                if response.status_code != 200:
                    return {"error": f"GitHub API returned HTTP {response.status_code}"}

                return response.json()

        except httpx.TimeoutException:
            return {"error": f"GitHub API request timed out after {timeout}s"}
        except Exception as exc:
            return {"error": f"GitHub API request failed: {exc}"}

    async def _fetch_repos(self, username: str, timeout: int) -> list[dict[str, Any]]:
        """Fetch user's public repositories."""
        url = f"{GITHUB_API_BASE}/users/{username}/repos"
        params = {"per_page": 30, "sort": "updated", "direction": "desc"}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url, headers=self._get_headers(), params=params
                )

                if response.status_code != 200:
                    return []

                repos = response.json()
                return [
                    {
                        "name": repo.get("name", ""),
                        "description": repo.get("description", ""),
                        "language": repo.get("language", ""),
                        "stargazers_count": repo.get("stargazers_count", 0),
                        "forks_count": repo.get("forks_count", 0),
                        "created_at": repo.get("created_at", ""),
                        "updated_at": repo.get("updated_at", ""),
                        "html_url": repo.get("html_url", ""),
                    }
                    for repo in repos
                ]

        except Exception:
            return []

    async def _fetch_orgs(self, username: str, timeout: int) -> list[dict[str, Any]]:
        """Fetch user's organization memberships."""
        url = f"{GITHUB_API_BASE}/users/{username}/orgs"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, headers=self._get_headers())

                if response.status_code != 200:
                    return []

                orgs = response.json()
                return [
                    {
                        "login": org.get("login", ""),
                        "description": org.get("description", ""),
                        "blog": org.get("blog", ""),
                    }
                    for org in orgs
                ]

        except Exception:
            return []
