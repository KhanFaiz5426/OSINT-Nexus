"""Search collector — Public web search for OSINT discovery.

Uses DuckDuckGo HTML search (no API key required) to discover publicly
indexed information about investigation targets. Extracts result titles,
URLs, and snippets for entity discovery and correlation.

Falls back gracefully when the search source is unavailable.
"""

from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import OSINTCollector
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
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


class SearchCollector(OSINTCollector):
    """Public web search collector using DuckDuckGo HTML endpoint."""

    name = "search"
    version = "1.0.0"
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

        query = self._build_query(target, target_type)
        return await _execute_single_search(query, target, target_type, self.name, self.version)

    async def _execute_search_query(
        self,
        client: httpx.AsyncClient,
        query: str,
    ) -> list[dict[str, str]]:
        """Execute a single DuckDuckGo search and return parsed results."""
        try:
            response = await client.post(
                DDG_HTML_URL,
                data={"q": query, "b": ""},
                headers={
                    "User-Agent": USER_AGENT,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )

            if response.status_code in (200, 203):
                return self._parse_html_results(response.text)
        except Exception as exc:
            logger.debug("Search query failed: %s", exc)

        return []

    def _build_query(self, target: str, target_type: TargetType) -> str:
        """Build a search query appropriate for the target type."""
        if target_type == TargetType.DOMAIN:
            return f"site:{target}"
        elif target_type in (
            TargetType.IP, TargetType.URL, TargetType.USERNAME,
            TargetType.EMAIL, TargetType.ORGANIZATION
        ):
            return f'"{target}"'
        return target

    def _parse_html_results(self, html: str) -> list[dict[str, str]]:
        """Parse DuckDuckGo HTML search results."""
        results: list[dict[str, str]] = []
        try:
            soup = BeautifulSoup(html, "html.parser")

            # DuckDuckGo HTML results are in div.result__body
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
                        from urllib.parse import unquote

                        url = unquote(match.group(1))

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                })

        except Exception as exc:
            logger.debug("Failed to parse DuckDuckGo HTML: %s", exc)

        return results[:10]  # Limit to top 10 results

    def _extract_entities_from_results(
        self, results: list[dict[str, str]]
    ) -> dict[str, list[str]]:
        """Extract entities (domains, emails, URLs, IPs) from search results."""
        domains: set[str] = set()
        emails: set[str] = set()
        urls: set[str] = set()
        ips: set[str] = set()

        for result in results:
            text = f"{result.get('title', '')} {result.get('snippet', '')} {result.get('url', '')}"

            # Extract domains
            for match in _DOMAIN_RE.finditer(text):
                d = match.group(0).lower()
                # Filter out common false positives
                if not any(
                    d.endswith(ext)
                    for ext in (".css", ".js", ".png", ".jpg", ".gif", ".svg", ".ico")
                ):
                    domains.add(d)

            # Extract emails
            for match in _EMAIL_RE.finditer(text):
                emails.add(match.group(0).lower())

            # Extract URLs
            for match in _URL_RE.finditer(text):
                urls.add(match.group(0))

            # Extract IPs
            for match in _IP_RE.finditer(text):
                ips.add(match.group(0))

        return {
            "domains": sorted(domains),
            "emails": sorted(emails),
            "urls": sorted(urls),
            "ips": sorted(ips),
        }


async def _execute_single_search(
    query: str,
    target: str,
    target_type: TargetType,
    collector_name: str,
    collector_version: str,
) -> RawResult:
    """Execute a single DuckDuckGo search query."""
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
        ) as client:
            response = await client.post(
                DDG_HTML_URL,
                data={"q": query, "b": ""},
                headers={
                    "User-Agent": USER_AGENT,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )

            if response.status_code == 203:
                return RawResult(
                    collector_name=collector_name,
                    collector_version=collector_version,
                    target=target,
                    target_type=target_type,
                    query=f"search:{query}",
                    status=ObservationStatus.ERROR,
                    error_message="DuckDuckGo returned 203 (bot detection)",
                )

            if response.status_code != 200:
                return RawResult(
                    collector_name=collector_name,
                    collector_version=collector_version,
                    target=target,
                    target_type=target_type,
                    query=f"search:{query}",
                    status=ObservationStatus.ERROR,
                    error_message=f"DuckDuckGo returned HTTP {response.status_code}",
                )

            # Parse results using the collector's parser
            import re as _re

            results: list[dict[str, str]] = []
            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")
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

                    if "uddg=" in href:
                        m = _re.search(r"uddg=([^&]+)", href)
                        if m:
                            from urllib.parse import unquote

                            url = unquote(m.group(1))

                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                    })
            except Exception:
                pass

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
                    metadata={"message": "No search results found"},
                )

            # Extract entities
            domains: set[str] = set()
            emails: set[str] = set()
            urls_set: set[str] = set()
            ips: set[str] = set()

            for result in results:
                text = f"{result.get('title', '')} {result.get('snippet', '')} {result.get('url', '')}"
                for match in _DOMAIN_RE.finditer(text):
                    d = match.group(0).lower()
                    if not any(d.endswith(ext) for ext in (".css", ".js", ".png", ".jpg", ".gif", ".svg", ".ico")):
                        domains.add(d)
                for match in _EMAIL_RE.finditer(text):
                    emails.add(match.group(0).lower())
                for match in _URL_RE.finditer(text):
                    urls_set.add(match.group(0))
                for match in _IP_RE.finditer(text):
                    ips.add(match.group(0))

            extracted = {
                "domains": sorted(domains),
                "emails": sorted(emails),
                "urls": sorted(urls_set),
                "ips": sorted(ips),
            }

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
                    "domains_found": len(domains),
                    "emails_found": len(emails),
                    "urls_found": len(urls_set),
                },
            )

    except httpx.TimeoutException:
        return RawResult(
            collector_name=collector_name,
            collector_version=collector_version,
            target=target,
            target_type=target_type,
            query=f"search:{query}",
            status=ObservationStatus.TIMEOUT,
            error_message="DuckDuckGo search timed out",
        )
    except Exception as exc:
        logger.exception("Search collection failed for %s", target)
        return RawResult(
            collector_name=collector_name,
            collector_version=collector_version,
            target=target,
            target_type=target_type,
            query=f"search:{query}",
            status=ObservationStatus.ERROR,
            error_message=f"Search collection failed: {exc}",
        )


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
        timeout=15,
        follow_redirects=True,
    ) as client:
        for q_info in queries[:8]:  # Limit to 8 queries per invocation
            query = q_info["query"]
            try:
                response = await client.post(
                    DDG_HTML_URL,
                    data={"q": query, "b": ""},
                    headers={
                        "User-Agent": USER_AGENT,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )

                if response.status_code != 200:
                    continue

                import re as _re

                results: list[dict[str, str]] = []
                try:
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(response.text, "html.parser")
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

                        if "uddg=" in href:
                            m = _re.search(r"uddg=([^&]+)", href)
                            if m:
                                from urllib.parse import unquote

                                url = unquote(m.group(1))

                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                            "source_query": q_info["description"],
                        })
                except Exception:
                    pass

                # Extract entities
                for result in results:
                    text = f"{result.get('title', '')} {result.get('snippet', '')} {result.get('url', '')}"
                    for match in _DOMAIN_RE.finditer(text):
                        d = match.group(0).lower()
                        if not any(d.endswith(ext) for ext in (".css", ".js", ".png", ".jpg", ".gif", ".svg", ".ico")):
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

            except Exception as exc:
                logger.debug("Username search query failed: %s", exc)
                continue

    if not all_results:
        return RawResult(
            collector_name="search",
            collector_version="1.0.0",
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
        collector_version="1.0.0",
        target=target,
        target_type=target_type,
        query=f"search:username:{target}",
        status=ObservationStatus.SUCCESS,
        raw_response={
            "query": f"username:{target}",
            "results": all_results[:50],  # Cap at 50 results
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
