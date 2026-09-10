"""SearXNG search provider — external metasearch via HTTP JSON API.

Calls a running SearXNG instance's ``/search`` endpoint with ``format=json``.
SearXNG source is NOT copied into OSINT Nexus; this module only makes HTTP
requests to a separately deployed SearXNG container.

SearXNG is optional: if the configured base URL is unreachable, the provider
returns an error status and zero results. The multi-provider orchestrator
proceeds with other providers.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.collectors.search_providers.base import (
    ProviderStatus,
    ProviderStatusCode,
    SearchProvider,
    SearchProviderResponse,
    SearchRequest,
    SearchResult,
)

logger = logging.getLogger(__name__)

# SearXNG JSON response keys (documented at https://docs.searxng.org/dev/search_api.html)
_RESULT_KEYS = ("title", "url", "content")


class SearXNGProvider(SearchProvider):
    """SearXNG metasearch provider.

    Args:
        base_url: Root URL of the SearXNG instance (e.g. ``http://searxng:8080``).
                  Must NOT include ``/search``.
    """

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "searxng"

    async def search(self, request: SearchRequest) -> SearchProviderResponse:
        """Query SearXNG JSON API and return normalized results."""
        start = time.monotonic()
        search_url = f"{self._base_url}/search"

        try:
            async with httpx.AsyncClient(timeout=request.timeout) as client:
                resp = await client.get(
                    search_url,
                    params={
                        "q": request.query,
                        "format": "json",
                        "categories": "general",
                        "language": "en",
                        "pageno": "1",
                    },
                    headers={
                        "Accept": "application/json",
                        "X-Forwarded-For": "127.0.0.1",
                        "X-Real-IP": "127.0.0.1",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            elapsed = time.monotonic() - start
            results = _parse_searxng_results(data, request.max_results)

            # Tag every result with provider name
            tagged: list[SearchResult] = []
            for i, r in enumerate(results):
                tagged.append(
                    SearchResult(
                        title=r["title"],
                        url=r["url"],
                        snippet=r.get("snippet", ""),
                        provider=self.name,
                        engine=r.get("engine", ""),
                        rank=i,
                    )
                )

            return SearchProviderResponse(
                provider_name=self.name,
                results=tagged,
                status=ProviderStatus(
                    provider_name=self.name,
                    status=ProviderStatusCode.SUCCESS,
                    result_count=len(tagged),
                    elapsed_seconds=round(elapsed, 3),
                ),
            )

        except httpx.TimeoutException as exc:
            elapsed = time.monotonic() - start
            logger.info("SearXNG timed out after %.1fs: %s", elapsed, exc)
            return SearchProviderResponse(
                provider_name=self.name,
                results=[],
                status=ProviderStatus(
                    provider_name=self.name,
                    status=ProviderStatusCode.TIMEOUT,
                    error_message=f"Timeout: {exc}",
                    elapsed_seconds=round(elapsed, 3),
                ),
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.info("SearXNG unavailable (%s) — continuing without it", exc)
            return SearchProviderResponse(
                provider_name=self.name,
                results=[],
                status=ProviderStatus(
                    provider_name=self.name,
                    status=ProviderStatusCode.ERROR,
                    error_message=str(exc),
                    elapsed_seconds=round(elapsed, 3),
                ),
            )

    async def health_check(self) -> dict[str, Any]:
        """Verify SearXNG is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/healthz")
                return {
                    "provider": self.name,
                    "available": resp.status_code < 400,
                    "base_url": self._base_url,
                    "status_code": resp.status_code,
                }
        except Exception as exc:
            return {
                "provider": self.name,
                "available": False,
                "base_url": self._base_url,
                "error": str(exc),
            }


def _parse_searxng_results(data: dict, max_results: int = 10) -> list[dict[str, str]]:
    """Parse SearXNG JSON response into normalized dicts.

    SearXNG response format:
    {
        "results": [
            {"title": "...", "url": "...", "content": "...", "engine": "google", ...},
            ...
        ],
        "number_of_results": 12345,
        ...
    }
    """
    results: list[dict[str, str]] = []
    raw_results = data.get("results", [])

    for item in raw_results[:max_results]:
        if not isinstance(item, dict):
            continue

        title = item.get("title", "")
        url = item.get("url", "")

        if not url:
            continue

        snippet = item.get("content", "")

        results.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
                "engine": item.get("engine", "unknown"),
            }
        )

    return results
