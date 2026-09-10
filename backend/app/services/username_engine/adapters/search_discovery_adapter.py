"""Search discovery adapter — discover platform profiles via web search.

For platforms where direct HTTP probing is unreliable (bot detection,
JavaScript rendering, authentication walls), this adapter uses web
search to discover whether a username profile URL appears in search
engine results.

IMPORTANT: This adapter does NOT confirm a profile exists. It discovers
that a URL *may* exist. The confidence is deliberately lower than
API or direct-HTTP evidence because:
- Search results can be stale
- URLs in search results may not resolve
- A search result does not prove the account is active

Provenance: results from this adapter carry evidence_confidence=LOW
and acquisition_method=search_discovery. Downstream consumers should
treat these as leads to investigate, not confirmed findings.

Currently configured platforms:
- X/Twitter (x_twitter): best candidate — consistent URL structure,
  high search index coverage, but heavy bot protection on direct access.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse

from app.services.username_engine.adapters.base import (
    AcquisitionMethod,
    AdapterResult,
    EvidenceConfidence,
    PlatformAdapter,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Platform-specific search configurations
_SEARCH_CONFIGS: dict[str, dict[str, Any]] = {
    "x_twitter": {
        "name": "X/Twitter",
        "url_pattern": "https://x.com/{username}",
        "search_queries": [
            'site:x.com "{username}"',
            'site:twitter.com "{username}"',
            '"{username}" site:x.com OR site:twitter.com profile',
        ],
        "url_patterns_to_match": [
            r"x\.com/[a-zA-Z0-9_]+$",
            r"twitter\.com/[a-zA-Z0-9_]+$",
        ],
        "negative_indicators": [
            "this account doesn't exist",
            "account suspended",
            "page doesn't exist",
        ],
        "base_confidence": 0.55,
    },
    "linkedin": {
        "name": "LinkedIn",
        "url_pattern": "https://www.linkedin.com/in/{username}/",
        "search_queries": [
            'site:linkedin.com/in "{username}"',
            '"{username}" site:linkedin.com profile',
        ],
        "url_patterns_to_match": [
            r"linkedin\.com/in/[a-zA-Z0-9_-]+$",
        ],
        "negative_indicators": [
            "page not found",
            "profile not found",
        ],
        "base_confidence": 0.50,
    },
    "instagram": {
        "name": "Instagram",
        "url_pattern": "https://www.instagram.com/{username}/",
        "search_queries": [
            'site:instagram.com "{username}"',
            '"{username}" instagram profile',
        ],
        "url_patterns_to_match": [
            r"instagram\.com/[a-zA-Z0-9_.]+$",
        ],
        "negative_indicators": [
            "sorry, this page isn't available",
            "the link you followed may be broken",
        ],
        "base_confidence": 0.50,
    },
    "tiktok": {
        "name": "TikTok",
        "url_pattern": "https://www.tiktok.com/@{username}",
        "search_queries": [
            'site:tiktok.com "@{username}"',
            '"{username}" tiktok profile',
        ],
        "url_patterns_to_match": [
            r"tiktok\.com/@[a-zA-Z0-9_.]+$",
        ],
        "negative_indicators": [
            "couldn't find this account",
            "page not available",
        ],
        "base_confidence": 0.50,
    },
}


class SearchDiscoveryAdapter(PlatformAdapter):
    """Adapter that discovers profiles via web search engines.

    Uses DuckDuckGo (and optionally SearXNG) to search for profile URLs
    on platforms that resist direct HTTP probing. Results are lower
    confidence than API or direct-HTTP evidence.

    This adapter does NOT bypass any platform protections — it relies
    entirely on publicly indexed search results.
    """

    def __init__(self) -> None:
        self._orchestrator = self._build_orchestrator()

    @property
    def name(self) -> str:
        return "search_discovery"

    @property
    def acquisition_method(self) -> AcquisitionMethod:
        return AcquisitionMethod.SEARCH_DISCOVERY

    @property
    def supported_platforms(self) -> list[str]:
        return list(_SEARCH_CONFIGS.keys())

    def _build_orchestrator(self) -> Any:
        """Build multi-provider search orchestrator."""
        from app.collectors.search_providers.base import SearchProvider
        from app.collectors.search_providers.duckduckgo import DuckDuckGoProvider
        from app.collectors.search_providers.orchestrator import (
            MultiProviderOrchestrator,
        )

        providers: list[SearchProvider] = [DuckDuckGoProvider()]

        try:
            from app.core.config import get_settings
            settings = get_settings()
            searxng_url = getattr(settings, "SEARXNG_BASE_URL", "")
            searxng_enabled = getattr(settings, "SEARXNG_ENABLED", True)
            if searxng_url and searxng_enabled:
                from app.collectors.search_providers.searxng import SearXNGProvider
                providers.append(SearXNGProvider(base_url=searxng_url))
        except Exception:
            pass

        return MultiProviderOrchestrator(providers)

    async def probe(
        self,
        platform_key: str,
        username: str,
        investigation_id: str,
    ) -> AdapterResult | None:
        """Discover a profile via web search."""
        if platform_key not in _SEARCH_CONFIGS:
            return None

        config = _SEARCH_CONFIGS[platform_key]
        url = config["url_pattern"].format(username=username)

        from app.collectors.search_providers.base import SearchRequest

        all_results: list[dict[str, str]] = []

        for query_template in config["search_queries"]:
            query = query_template.replace("{username}", username)
            request = SearchRequest(
                query=query,
                max_results=5,
                timeout=10.0,
            )

            try:
                orch_result = await self._orchestrator.search(request)
                for sr in orch_result.results:
                    all_results.append({
                        "title": sr.title,
                        "url": sr.url,
                        "snippet": sr.snippet,
                    })
            except Exception as exc:
                logger.debug("Search failed for '%s': %s", query, exc)

            # Rate limit between queries
            await asyncio.sleep(0.5)

        if not all_results:
            return AdapterResult(
                platform_key=platform_key,
                platform_name=config["name"],
                username=username,
                found=False,
                url=url,
                acquisition_method=self.acquisition_method,
                evidence_confidence=EvidenceConfidence.LOW,
                evidence={
                    "queries_run": len(config["search_queries"]),
                    "results_found": 0,
                },
            )

        # Analyze results for matching profile URLs
        matching_urls: list[dict[str, str]] = []
        negative_signals: list[str] = []

        for result in all_results:
            result_url = result.get("url", "")
            snippet = result.get("snippet", "").lower()
            title = result.get("title", "").lower()
            text = f"{title} {snippet}"

            # Check for negative indicators first — skip this result if found
            has_negative = False
            for indicator in config["negative_indicators"]:
                if indicator.lower() in text:
                    negative_signals.append(indicator)
                    has_negative = True
                    break

            if has_negative:
                continue

            # Check if URL matches expected profile pattern
            for pattern in config["url_patterns_to_match"]:
                if re.search(pattern, result_url, re.IGNORECASE):
                    # Additional check: URL should contain the username
                    parsed = urlparse(result_url)
                    path_parts = [p for p in parsed.path.split("/") if p]
                    if username.lower() in [
                        p.lower().lstrip("@") for p in path_parts
                    ]:
                        matching_urls.append(result)
                        break

        if not matching_urls:
            return AdapterResult(
                platform_key=platform_key,
                platform_name=config["name"],
                username=username,
                found=False,
                url=url,
                acquisition_method=self.acquisition_method,
                evidence_confidence=EvidenceConfidence.LOW,
                evidence={
                    "queries_run": len(config["search_queries"]),
                    "results_found": len(all_results),
                    "matching_urls": 0,
                    "negative_signals": negative_signals,
                },
            )

        # Found matching URLs — return with LOW confidence
        best_match = matching_urls[0]
        confidence = config["base_confidence"]

        # Slightly higher confidence if multiple sources found it
        if len(matching_urls) > 1:
            confidence = min(confidence + 0.05, 0.65)

        # Slightly higher if the snippet mentions the username
        for match in matching_urls:
            if username.lower() in match.get("snippet", "").lower():
                confidence = min(confidence + 0.03, 0.65)
                break

        return AdapterResult(
            platform_key=platform_key,
            platform_name=config["name"],
            username=username,
            found=True,
            url=best_match.get("url", url),
            acquisition_method=self.acquisition_method,
            status_code=200,
            confidence=confidence,
            evidence_confidence=EvidenceConfidence.LOW,
            evidence={
                "queries_run": len(config["search_queries"]),
                "results_found": len(all_results),
                "matching_urls": len(matching_urls),
                "best_match_title": best_match.get("title", ""),
                "best_match_snippet": best_match.get("snippet", "")[:200],
                "negative_signals": negative_signals,
                "warning": (
                    "Search-discovered URL — not confirmed via direct access. "
                    "May be stale, removed, or require authentication."
                ),
            },
            profile={
                "name": username,
                "platform": config["name"],
                "url": best_match.get("url", url),
                "title": best_match.get("title", ""),
                "snippet": best_match.get("snippet", "")[:200],
                "discovery_method": "web_search",
            },
        )
