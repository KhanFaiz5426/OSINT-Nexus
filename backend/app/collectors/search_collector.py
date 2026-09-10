"""Search collector — Public web search for OSINT discovery.

Uses a multi-provider search layer to discover publicly indexed information
about investigation targets. Providers include DuckDuckGo (always available)
and SearXNG (optional, configured via SEARXNG_BASE_URL).

Query generation is target-type-specific. Search execution is delegated to
the pluggable SearchProvider implementations via the MultiProviderOrchestrator.
Entity extraction from results is performed post-search.

Falls back gracefully: if SearXNG is unavailable, DuckDuckGo results are
still returned. If all providers fail, returns empty success.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from app.collectors.base import OSINTCollector
from app.collectors.search_providers.base import (
    SearchProvider,
    SearchRequest,
    SearchResult,
)
from app.collectors.search_providers.duckduckgo import DuckDuckGoProvider
from app.collectors.search_providers.orchestrator import (
    MultiProviderOrchestrator,
    OrchestratorResult,
)
from app.collectors.search_providers.searxng import SearXNGProvider
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)

# Regex patterns for extracting entities from search snippets
_DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b", re.IGNORECASE
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_IP_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

# File extensions to exclude from domain extraction
_EXCLUDE_EXTS = (".css", ".js", ".png", ".jpg", ".gif", ".svg", ".ico")


def _get_search_config() -> dict[str, Any]:
    """Load search provider configuration from environment/settings."""
    try:
        from app.core.config import get_settings
        settings = get_settings()
        return {
            "searxng_base_url": getattr(settings, "SEARXNG_BASE_URL", ""),
            "searxng_enabled": getattr(settings, "SEARXNG_ENABLED", True),
            "provider_timeout": getattr(settings, "SEARCH_PROVIDER_TIMEOUT", 10.0),
            "max_results_per_provider": getattr(
                settings, "SEARCH_MAX_RESULTS_PER_PROVIDER", 10
            ),
        }
    except Exception:
        return {
            "searxng_base_url": "",
            "searxng_enabled": True,
            "provider_timeout": 10.0,
            "max_results_per_provider": 10,
        }


def _build_providers(config: dict[str, Any]) -> list[SearchProvider]:
    """Create enabled search provider instances from configuration."""
    providers: list[SearchProvider] = [DuckDuckGoProvider()]

    searxng_url = config.get("searxng_base_url", "")
    searxng_enabled = config.get("searxng_enabled", True)

    if searxng_url and searxng_enabled:
        providers.append(SearXNGProvider(base_url=searxng_url))
        logger.info("SearXNG provider enabled at %s", searxng_url)
    else:
        logger.debug("SearXNG provider not configured or disabled")

    return providers


class SearchCollector(OSINTCollector):
    """Public web search collector using multiple search providers.

    Delegates search execution to the multi-provider orchestrator which
    runs enabled providers concurrently. Query generation remains
    target-type-specific.
    """

    name = "search"
    version = "1.2.0"
    supported_target_types = [
        TargetType.DOMAIN,
        TargetType.IP,
        TargetType.URL,
        TargetType.USERNAME,
        TargetType.EMAIL,
        TargetType.ORGANIZATION,
    ]
    requires_api_key = False
    cache_ttl = 7200  # 2 hours — search results change moderately
    rate_limit_rpm = 10  # Respect search engine capacity

    def __init__(self, cache=None) -> None:
        super().__init__(cache=cache)
        config = _get_search_config()
        self._providers = _build_providers(config)
        self._orchestrator = MultiProviderOrchestrator(self._providers)
        self._provider_timeout = config.get("provider_timeout", 10.0)
        self._max_results = config.get("max_results_per_provider", 10)

    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        if target_type == TargetType.USERNAME:
            return await self._collect_username_searches(target, target_type)

        query = _build_query(target, target_type)
        request = SearchRequest(
            query=query,
            max_results=self._max_results,
            timeout=self._provider_timeout,
        )

        orch_result = await self._orchestrator.search(request)
        return self._make_raw_result(
            orch_result, query, target, target_type, source="multi_provider"
        )

    def _build_query(self, target: str, target_type: TargetType) -> str:
        return _build_query(target, target_type)

    async def _collect_username_searches(
        self, target: str, target_type: TargetType
    ) -> RawResult:
        """Run multiple search queries for a username target.

        Queries are generated by the username_variations module.
        Each query is executed through the multi-provider orchestrator.
        """
        from app.services.username_variations import generate_search_queries

        queries = generate_search_queries(target, max_queries=12)

        all_results: list[dict] = []
        all_extracted: dict[str, set[str]] = {
            "domains": set(),
            "emails": set(),
            "urls": set(),
            "ips": set(),
        }
        provider_statuses: list[dict] = []

        for q_info in queries[:8]:  # Limit to 8 queries per invocation
            query = q_info["query"]
            request = SearchRequest(
                query=query,
                max_results=self._max_results,
                timeout=self._provider_timeout,
            )

            orch_result = await self._orchestrator.search(request)

            # Convert SearchResult dataclasses to dicts for RawResult
            for sr in orch_result.results:
                r = {
                    "title": sr.title,
                    "url": sr.url,
                    "snippet": sr.snippet,
                    "provider": sr.provider,
                    "engine": sr.engine,
                    "source_query": q_info["description"],
                }
                all_results.append(r)

                # Extract entities
                text = f"{sr.title} {sr.snippet} {sr.url}"
                for match in _DOMAIN_RE.finditer(text):
                    d = match.group(0).lower()
                    if not any(d.endswith(ext) for ext in _EXCLUDE_EXTS):
                        all_extracted["domains"].add(d)
                for match in _EMAIL_RE.finditer(text):
                    all_extracted["emails"].add(match.group(0).lower())
                for match in _URL_RE.finditer(text):
                    all_extracted["urls"].add(match.group(0))
                for match in _IP_RE.finditer(text):
                    all_extracted["ips"].add(match.group(0))

            # Record provider statuses
            for ps in orch_result.provider_statuses:
                provider_statuses.append({
                    "provider": ps.provider_name,
                    "status": ps.status,
                    "result_count": ps.result_count,
                    "query": query,
                })

            # Rate limit between queries
            await asyncio.sleep(1.0)

        if not all_results:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"search:username:{target}",
                status=ObservationStatus.SUCCESS,
                raw_response={
                    "query": f"username:{target}",
                    "results": [],
                    "result_count": 0,
                    "queries_run": len(queries[:8]),
                },
                normalized_value=target,
                confidence=0.3,
                metadata={
                    "message": "No search results found",
                    "queries_run": len(queries[:8]),
                    "providers": self._orchestrator.provider_names,
                },
            )

        return RawResult(
            collector_name=self.name,
            collector_version=self.version,
            target=target,
            target_type=target_type,
            query=f"search:username:{target}",
            status=ObservationStatus.SUCCESS,
            raw_response={
                "query": f"username:{target}",
                "results": all_results[:50],
                "result_count": len(all_results),
                "extracted_entities": {
                    "domains": sorted(all_extracted["domains"]),
                    "emails": sorted(all_extracted["emails"]),
                    "urls": sorted(all_extracted["urls"]),
                    "ips": sorted(all_extracted["ips"]),
                },
                "queries_run": len(queries[:8]),
            },
            normalized_value=target,
            confidence=0.7,
            metadata={
                "result_count": len(all_results),
                "domains_found": len(all_extracted["domains"]),
                "emails_found": len(all_extracted["emails"]),
                "urls_found": len(all_extracted["urls"]),
                "queries_run": len(queries[:8]),
                "providers": self._orchestrator.provider_names,
            },
        )

    def _make_raw_result(
        self,
        orch_result: OrchestratorResult,
        query: str,
        target: str,
        target_type: TargetType,
        *,
        source: str = "multi_provider",
    ) -> RawResult:
        """Convert orchestrator output to a RawResult for the pipeline."""
        # Convert SearchResult dataclasses to dicts
        results_dicts = [
            {
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "provider": r.provider,
                "engine": r.engine,
            }
            for r in orch_result.results
        ]

        if not results_dicts:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"search:{query}",
                status=ObservationStatus.SUCCESS,
                raw_response={"query": query, "results": [], "result_count": 0},
                normalized_value=target,
                confidence=0.3,
                metadata={
                    "message": "No search results found",
                    "source": source,
                    "providers": self._orchestrator.provider_names,
                    "provider_statuses": [
                        {
                            "provider": ps.provider_name,
                            "status": ps.status,
                            "result_count": ps.result_count,
                        }
                        for ps in orch_result.provider_statuses
                    ],
                },
            )

        extracted = _extract_entities(results_dicts)

        return RawResult(
            collector_name=self.name,
            collector_version=self.version,
            target=target,
            target_type=target_type,
            query=f"search:{query}",
            status=ObservationStatus.SUCCESS,
            raw_response={
                "query": query,
                "results": results_dicts,
                "result_count": len(results_dicts),
                "extracted_entities": extracted,
                "total_raw_results": orch_result.total_raw_results,
                "deduplicated_count": orch_result.deduplicated_count,
            },
            normalized_value=target,
            confidence=0.7,
            metadata={
                "result_count": len(results_dicts),
                "domains_found": len(extracted["domains"]),
                "emails_found": len(extracted["emails"]),
                "urls_found": len(extracted["urls"]),
                "source": source,
                "providers": self._orchestrator.provider_names,
                "provider_statuses": [
                    {
                        "provider": ps.provider_name,
                        "status": ps.status,
                        "result_count": ps.result_count,
                    }
                    for ps in orch_result.provider_statuses
                ],
            },
        )


# ── Shared helpers ───────────────────────────────────────────────────────────


def _build_query(target: str, target_type: TargetType) -> str:
    """Build a search query appropriate for the target type."""
    if target_type == TargetType.DOMAIN:
        return f"site:{target}"
    elif target_type == TargetType.ORGANIZATION:
        return f'"{target}" company OR organization OR official'
    elif target_type in (
        TargetType.IP, TargetType.URL, TargetType.USERNAME,
        TargetType.EMAIL,
    ):
        return f'"{target}"'
    return target


def _extract_entities(results: list[dict[str, str]]) -> dict[str, list[str]]:
    """Extract entities (domains, emails, URLs, IPs) from search results."""
    domains: set[str] = set()
    emails: set[str] = set()
    urls: set[str] = set()
    ips: set[str] = set()

    for result in results:
        text = f"{result.get('title', '')} {result.get('snippet', '')} {result.get('url', '')}"

        for match in _DOMAIN_RE.finditer(text):
            d = match.group(0).lower()
            if not any(d.endswith(ext) for ext in _EXCLUDE_EXTS):
                domains.add(d)

        for match in _EMAIL_RE.finditer(text):
            emails.add(match.group(0).lower())

        for match in _URL_RE.finditer(text):
            urls.add(match.group(0))

        for match in _IP_RE.finditer(text):
            ips.add(match.group(0))

    return {
        "domains": sorted(domains),
        "emails": sorted(emails),
        "urls": sorted(urls),
        "ips": sorted(ips),
    }
