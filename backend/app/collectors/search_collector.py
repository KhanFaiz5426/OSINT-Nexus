"""Search collector — Public web search for OSINT discovery.

Uses DuckDuckGo HTML search (no API key required) to discover publicly
indexed information about investigation targets. Extracts result titles,
URLs, and snippets for entity discovery and correlation.

Falls back to DuckDuckGo Instant Answer JSON API and DDG Lite endpoint
when the primary HTML endpoint is unavailable or rate-limited.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import OSINTCollector
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"
DDG_API_URL = "https://api.duckduckgo.com/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

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


class SearchCollector(OSINTCollector):
    """Public web search collector using DuckDuckGo with multiple fallbacks."""

    name = "search"
    version = "1.1.0"
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
    rate_limit_rpm = 10  # Respect DuckDuckGo capacity

    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        if target_type == TargetType.USERNAME:
            return await _collect_username_searches(target, target_type)

        query = _build_query(target, target_type)
        return await _execute_search_with_fallbacks(
            query, target, target_type, self.name, self.version
        )

    def _build_query(self, target: str, target_type: TargetType) -> str:
        return _build_query(target, target_type)


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


def _parse_ddg_html(html: str) -> list[dict[str, str]]:
    """Parse DuckDuckGo HTML search results (shared by all DDG endpoints)."""
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

            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
            })

    except Exception as exc:
        logger.debug("Failed to parse DuckDuckGo HTML: %s", exc)

    return results[:10]


def _parse_ddg_lite_html(html: str) -> list[dict[str, str]]:
    """Parse DuckDuckGo Lite HTML results (simpler format)."""
    results: list[dict[str, str]] = []
    try:
        soup = BeautifulSoup(html, "html.parser")

        # DDG Lite uses table rows
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
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                })
    except Exception as exc:
        logger.debug("Failed to parse DuckDuckGo Lite: %s", exc)

    return results[:10]


def _parse_ddg_api_json(data: dict) -> list[dict[str, str]]:
    """Parse DuckDuckGo Instant Answer API JSON response."""
    results: list[dict[str, str]] = []

    # Abstract (main result)
    if data.get("Abstract"):
        results.append({
            "title": data.get("Heading", ""),
            "url": data.get("AbstractURL", ""),
            "snippet": data.get("Abstract", ""),
        })

    # Related topics
    for topic in data.get("RelatedTopics", []):
        if isinstance(topic, dict):
            if "Topics" in topic:
                # Subcategory
                for sub in topic.get("Topics", []):
                    if isinstance(sub, dict) and sub.get("Text"):
                        results.append({
                            "title": sub.get("Text", "")[:100],
                            "url": sub.get("FirstURL", ""),
                            "snippet": sub.get("Text", ""),
                        })
            elif topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:100],
                    "url": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", ""),
                })

    # Results section
    for res in data.get("Results", []):
        if isinstance(res, dict) and res.get("Text"):
            results.append({
                "title": res.get("Text", "")[:100],
                "url": res.get("FirstURL", ""),
                "snippet": res.get("Text", ""),
            })

    return results[:10]


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


def _make_result(
    results: list[dict[str, str]],
    query: str,
    target: str,
    target_type: TargetType,
    collector_name: str,
    collector_version: str,
    *,
    source: str = "html",
) -> RawResult:
    """Build a RawResult from parsed search results."""
    if not results:
        return RawResult(
            collector_name=collector_name,
            collector_version=collector_version,
            target=target,
            target_type=target_type,
            query=f"search:{query}",
            status=ObservationStatus.SUCCESS,
            raw_response={"query": query, "results": [], "result_count": 0},
            normalized_value=target,
            confidence=0.3,
            metadata={"message": "No search results found", "source": source},
        )

    extracted = _extract_entities(results)

    return RawResult(
        collector_name=collector_name,
        collector_version=collector_version,
        target=target,
        target_type=target_type,
        query=f"search:{query}",
        status=ObservationStatus.SUCCESS,
        raw_response={
            "query": query,
            "results": results,
            "result_count": len(results),
            "extracted_entities": extracted,
        },
        normalized_value=target,
        confidence=0.7,
        metadata={
            "result_count": len(results),
            "domains_found": len(extracted["domains"]),
            "emails_found": len(extracted["emails"]),
            "urls_found": len(extracted["urls"]),
            "source": source,
        },
    )


# ── Search execution with fallback chain ─────────────────────────────────────


async def _execute_search_with_fallbacks(
    query: str,
    target: str,
    target_type: TargetType,
    collector_name: str,
    collector_version: str,
) -> RawResult:
    """Execute search with fallback chain: HTML -> Lite -> API JSON.

    Falls back gracefully through multiple DuckDuckGo endpoints to maximize
    reliability. Each endpoint has different bot-detection characteristics.
    """
    async with httpx.AsyncClient(
        timeout=5.0,
        follow_redirects=True,
    ) as client:
        # ── Attempt 1: DDG HTML (best results) ───────────────────────────
        results = await _try_ddg_html(client, query)
        if results:
            return _make_result(
                results, query, target, target_type,
                collector_name, collector_version, source="html",
            )

        # ── Attempt 2: DDG Lite (simpler, less bot-detection) ────────────
        results = await _try_ddg_lite(client, query)
        if results:
            return _make_result(
                results, query, target, target_type,
                collector_name, collector_version, source="lite",
            )

        # ── Attempt 3: DDG Instant Answer API (JSON, no scraping) ────────
        results = await _try_ddg_api(client, query)
        if results:
            return _make_result(
                results, query, target, target_type,
                collector_name, collector_version, source="api",
            )

    # All fallbacks exhausted — return empty success
    return _make_result(
        [], query, target, target_type,
        collector_name, collector_version, source="all_failed",
    )


async def _try_ddg_html(
    client: httpx.AsyncClient, query: str
) -> list[dict[str, str]]:
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


async def _try_ddg_lite(
    client: httpx.AsyncClient, query: str
) -> list[dict[str, str]]:
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


async def _try_ddg_api(
    client: httpx.AsyncClient, query: str
) -> list[dict[str, str]]:
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


# ── Username multi-query search ──────────────────────────────────────────────


async def _collect_username_searches(
    target: str, target_type: TargetType
) -> RawResult:
    """Run multiple search queries for a username target.

    Queries:
    1. Exact username on key platforms (site: searches)
    2. Username variations
    3. General profile search
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

    async with httpx.AsyncClient(
        timeout=5.0,
        follow_redirects=True,
    ) as client:
        for q_info in queries[:8]:  # Limit to 8 queries per invocation
            query = q_info["query"]

            # Try HTML first, then fallbacks
            results = await _try_ddg_html(client, query)
            if not results:
                results = await _try_ddg_lite(client, query)
            if not results:
                results = await _try_ddg_api(client, query)

            # Add source_query metadata to each result
            for r in results:
                r["source_query"] = q_info["description"]

            # Extract entities from results
            for result in results:
                text = f"{result.get('title', '')} {result.get('snippet', '')} {result.get('url', '')}"
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

            all_results.extend(results)

            # Rate limit between queries
            import asyncio
            await asyncio.sleep(1.0)

    if not all_results:
        return RawResult(
            collector_name="search",
            collector_version="1.1.0",
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
            metadata={"message": "No search results found", "queries_run": len(queries[:8])},
        )

    return RawResult(
        collector_name="search",
        collector_version="1.1.0",
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
        },
    )
