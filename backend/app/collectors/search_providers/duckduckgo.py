"""DuckDuckGo search provider — HTML/Lite/API fallback chain.

Extracted from the original search_collector.py. Implements the SearchProvider
interface with the same 3-endpoint fallback logic:
  1. DDG HTML (best results, most bot-detection)
  2. DDG Lite (simpler format, less detection)
  3. DDG Instant Answer API (JSON, no scraping)

No API key required.
"""

from __future__ import annotations

import logging
import re
import time
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup

from app.collectors.search_providers.base import (
    ProviderStatus,
    ProviderStatusCode,
    SearchProvider,
    SearchProviderResponse,
    SearchRequest,
    SearchResult,
)

logger = logging.getLogger(__name__)

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"
DDG_API_URL = "https://api.duckduckgo.com/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class DuckDuckGoProvider(SearchProvider):
    """DuckDuckGo search with HTML → Lite → API fallback."""

    @property
    def name(self) -> str:
        return "duckduckgo"

    async def search(self, request: SearchRequest) -> SearchProviderResponse:
        """Execute search with fallback chain."""
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=request.timeout,
                follow_redirects=True,
            ) as client:
                # Attempt 1: DDG HTML
                raw = await _try_ddg_html(client, request.query)

                # Attempt 2: DDG Lite
                if not raw:
                    raw = await _try_ddg_lite(client, request.query)

                # Attempt 3: DDG API JSON
                if not raw:
                    raw = await _try_ddg_api(client, request.query)

            elapsed = time.monotonic() - start
            results = [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("snippet", ""),
                    provider=self.name,
                    rank=i,
                )
                for i, r in enumerate(raw[: request.max_results])
            ]

            return SearchProviderResponse(
                provider_name=self.name,
                results=results,
                status=ProviderStatus(
                    provider_name=self.name,
                    status=ProviderStatusCode.SUCCESS,
                    result_count=len(results),
                    elapsed_seconds=round(elapsed, 3),
                ),
            )

        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.warning("DuckDuckGo provider failed: %s", exc)
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

    async def health_check(self) -> dict:
        """Quick connectivity check."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.head(DDG_HTML_URL, headers={"User-Agent": USER_AGENT})
                return {
                    "provider": self.name,
                    "available": resp.status_code < 400,
                    "status_code": resp.status_code,
                }
        except Exception as exc:
            return {"provider": self.name, "available": False, "error": str(exc)}


# ── Endpoint helpers (extracted from original search_collector.py) ────────────


async def _try_ddg_html(client: httpx.AsyncClient, query: str) -> list[dict[str, str]]:
    """Attempt DDG HTML endpoint."""
    try:
        response = await client.post(
            DDG_HTML_URL,
            data={"q": query, "b": ""},
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        if response.status_code == 200:
            return _parse_ddg_html(response.text)
        if response.status_code == 203:
            logger.debug("DDG HTML returned 203 (bot detection), trying fallback")
    except Exception as exc:
        logger.debug("DDG HTML failed: %s", exc)
    return []


async def _try_ddg_lite(client: httpx.AsyncClient, query: str) -> list[dict[str, str]]:
    """Attempt DDG Lite endpoint (simpler format, less bot detection)."""
    try:
        response = await client.post(
            DDG_LITE_URL,
            data={"q": query},
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        if response.status_code == 200:
            return _parse_ddg_lite_html(response.text)
    except Exception as exc:
        logger.debug("DDG Lite failed: %s", exc)
    return []


async def _try_ddg_api(client: httpx.AsyncClient, query: str) -> list[dict[str, str]]:
    """Attempt DDG Instant Answer API (JSON, no scraping needed)."""
    try:
        response = await client.get(
            DDG_API_URL,
            params={
                "q": query,
                "format": "json",
                "no_redirect": "1",
                "no_html": "1",
                "skip_disambig": "1",
            },
            headers={"User-Agent": USER_AGENT},
        )
        if response.status_code == 200:
            data = response.json()
            return _parse_ddg_api_json(data)
    except Exception as exc:
        logger.debug("DDG API failed: %s", exc)
    return []


# ── Parsing helpers (moved verbatim from original search_collector.py) ────────


def _parse_ddg_html(html: str) -> list[dict[str, str]]:
    """Parse DuckDuckGo HTML search results."""
    results: list[dict[str, str]] = []
    try:
        soup = BeautifulSoup(html, "html.parser")

        for result_div in soup.select(".result__body"):
            title_el = result_div.select_one(".result__title a")
            snippet_el = result_div.select_one(".result__snippet")
            url_el = result_div.select_one(".result__url")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            url = url_el.get_text(strip=True) if url_el else ""
            href = title_el.get("href", "")

            # DuckDuckGo wraps URLs in redirect URLs; extract the actual URL
            if "uddg=" in href:
                match = re.search(r"uddg=([^&]+)", href)
                if match:
                    url = unquote(match.group(1))

            results.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                }
            )

    except Exception as exc:
        logger.debug("Failed to parse DuckDuckGo HTML: %s", exc)

    return results[:10]


def _parse_ddg_lite_html(html: str) -> list[dict[str, str]]:
    """Parse DuckDuckGo Lite HTML results (simpler format)."""
    results: list[dict[str, str]] = []
    try:
        soup = BeautifulSoup(html, "html.parser")

        for row in soup.select("tr"):
            link = row.select_one("a.result-link")
            snippet_td = row.select_one("td.result-snippet")

            if not link:
                continue

            title = link.get_text(strip=True)
            url = link.get("href", "")
            snippet = snippet_td.get_text(strip=True) if snippet_td else ""

            if "uddg=" in url:
                match = re.search(r"uddg=([^&]+)", url)
                if match:
                    url = unquote(match.group(1))

            if title:
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                    }
                )
    except Exception as exc:
        logger.debug("Failed to parse DuckDuckGo Lite: %s", exc)

    return results[:10]


def _parse_ddg_api_json(data: dict) -> list[dict[str, str]]:
    """Parse DuckDuckGo Instant Answer API JSON response."""
    results: list[dict[str, str]] = []

    # Abstract (main result)
    if data.get("Abstract"):
        results.append(
            {
                "title": data.get("Heading", ""),
                "url": data.get("AbstractURL", ""),
                "snippet": data.get("Abstract", ""),
            }
        )

    # Related topics
    for topic in data.get("RelatedTopics", []):
        if isinstance(topic, dict):
            if "Topics" in topic:
                for sub in topic.get("Topics", []):
                    if isinstance(sub, dict) and sub.get("Text"):
                        results.append(
                            {
                                "title": sub.get("Text", "")[:100],
                                "url": sub.get("FirstURL", ""),
                                "snippet": sub.get("Text", ""),
                            }
                        )
            elif topic.get("Text"):
                results.append(
                    {
                        "title": topic.get("Text", "")[:100],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", ""),
                    }
                )

    # Results section
    for res in data.get("Results", []):
        if isinstance(res, dict) and res.get("Text"):
            results.append(
                {
                    "title": res.get("Text", "")[:100],
                    "url": res.get("FirstURL", ""),
                    "snippet": res.get("Text", ""),
                }
            )

    return results[:10]
