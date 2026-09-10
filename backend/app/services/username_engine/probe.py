"""Username Probe Engine — internet-wide username discovery.

Three-phase approach:
1. WEB SEARCH: Query DuckDuckGo for the username across the internet
2. DOMAIN PROBING: Try personal domain patterns (name.dev, name.com, etc.)
3. PLATFORM PROBING: Direct HTTP checks on known platforms

Does not wrap Sherlock, WhatsMyName, Holehe, or any third-party tool.
All platform definitions are first-party data in ``platforms.json``.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.collectors.rate_limiter import TokenBucketRateLimiter
from app.models import ObservationStatus, RawResult, TargetType
from app.services.username_engine.intelligence import PlatformIntelligenceOrchestrator
from app.services.username_engine.models import (
    PlatformDefinition,
    ProbeBudget,
    ProbeResult,
)
from app.services.username_engine.platform_store import (
    get_enabled_platforms,
    load_platforms,
)

logger = logging.getLogger(__name__)

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"
DDG_API_URL = "https://api.duckduckgo.com/"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Known platform domains for URL classification
_PLATFORM_DOMAINS: dict[str, str] = {
    "github.com": "GitHub",
    "gitlab.com": "GitLab",
    "reddit.com": "Reddit",
    "twitter.com": "Twitter/X",
    "x.com": "Twitter/X",
    "instagram.com": "Instagram",
    "linkedin.com": "LinkedIn",
    "youtube.com": "YouTube",
    "medium.com": "Medium",
    "dev.to": "Dev.to",
    "stackoverflow.com": "StackOverflow",
    "stackexchange.com": "StackExchange",
    "twitch.tv": "Twitch",
    "t.me": "Telegram",
    "telegram.me": "Telegram",
    "keybase.io": "Keybase",
    "news.ycombinator.com": "HackerNews",
    "about.me": "About.me",
    "linktr.ee": "Linktree",
    "pinterest.com": "Pinterest",
    "tumblr.com": "Tumblr",
    "gravatar.com": "Gravatar",
    "en.gravatar.com": "Gravatar",
    "behance.net": "Behance",
    "dribbble.com": "Dribbble",
    "figma.com": "Figma",
    "notion.site": "Notion",
    "substack.com": "Substack",
    "hashnode.dev": "Hashnode",
    "producthunt.com": "ProductHunt",
    "goodreads.com": "Goodreads",
    "steamcommunity.com": "Steam",
    "open.spotify.com": "Spotify",
    "soundcloud.com": "SoundCloud",
    "flickr.com": "Flickr",
    "500px.com": "500px",
    "vimeo.com": "Vimeo",
    "npmjs.com": "npm",
    "crates.io": "Crates.io",
    "dockerhub.com": "DockerHub",
    "hub.docker.com": "DockerHub",
    "bitbucket.org": "Bitbucket",
    "codepen.io": "CodePen",
    "jsfiddle.net": "JSFiddle",
    "replit.com": "Replit",
    "leetcode.com": "LeetCode",
    "hackerrank.com": "HackerRank",
    "codewars.com": "Codewars",
    "kaggle.com": "Kaggle",
    "researchgate.net": "ResearchGate",
    "academia.edu": "Academia",
    "orcid.org": "ORCID",
    "scholar.google.com": "Google Scholar",
    "zhihu.com": "Zhihu",
    "quora.com": "Quora",
}


class UsernameProbeEngine:
    """Engine that discovers usernames across the internet.

    Phase 1: Web search to find profiles, portfolios, and mentions
    Phase 2: Personal domain pattern probing
    Phase 3: Direct platform URL probing
    """

    COLLECTOR_NAME = "username_probe"
    COLLECTOR_VERSION = "2.0.0"

    def __init__(self, budget: ProbeBudget | None = None) -> None:
        self.budget = budget or ProbeBudget()
        self._platforms = load_platforms()
        self._rate_limiters: dict[str, TokenBucketRateLimiter] = {}
        self._requests_made = 0
        self._intelligence = PlatformIntelligenceOrchestrator()

    async def probe_username(
        self,
        username: str,
        variations: list[str],
        investigation_id: str,
        *,
        max_platforms: int | None = None,
    ) -> list[RawResult]:
        """Discover username across the internet.

        Args:
            username: The original username target.
            variations: Confidence-ranked list of username variations to probe.
            investigation_id: Owning investigation UUID.
            max_platforms: Override budget.max_platforms for this run.

        Returns:
            List of RawResult objects for confirmed findings.
        """
        self._requests_made = 0
        results: list[RawResult] = []
        seen_urls: set[str] = set()

        # ── Phase 1: Web Search ──────────────────────────────────────────
        logger.info("Phase 1: Web search for '%s'", username)
        search_results = await self._web_search_phase(username, variations, investigation_id)
        for r in search_results:
            url = r.raw_response.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                results.append(r)
        logger.info("Web search found %d profiles", len(results))

        # ── Phase 2: Personal Domain Probing ─────────────────────────────
        logger.info("Phase 2: Personal domain probing for '%s'", username)
        domain_results = await self._domain_probing_phase(username, variations, investigation_id)
        for r in domain_results:
            url = r.raw_response.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                results.append(r)
        logger.info("Domain probing found %d profiles", len(domain_results))

        # ── Phase 3: Platform Probing ────────────────────────────────────
        if self._requests_made < self.budget.max_total_requests:
            logger.info("Phase 3: Platform probing for '%s'", username)
            platform_results = await self._platform_probing_phase(
                username, variations, investigation_id, max_platforms
            )
            for r in platform_results:
                url = r.raw_response.get("url", "")
                if url not in seen_urls:
                    seen_urls.add(url)
                    results.append(r)
            logger.info("Platform probing found %d profiles", len(platform_results))

        logger.info(
            "Probe complete: %d total findings from %d requests",
            len(results),
            self._requests_made,
        )
        return results

    # ── Phase 1: Web Search ──────────────────────────────────────────────────

    async def _web_search_phase(
        self,
        username: str,
        variations: list[str],
        investigation_id: str,
    ) -> list[RawResult]:
        """Search the internet for the username using DuckDuckGo."""
        results: list[RawResult] = []

        # Build search queries
        queries = self._build_search_queries(username, variations)

        async with httpx.AsyncClient(
            timeout=8.0,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            for query_info in queries:
                if self._requests_made >= self.budget.max_total_requests:
                    break

                query = query_info["query"]
                description = query_info["description"]

                search_results = await self._ddg_search(client, query)
                self._requests_made += 1

                for sr in search_results:
                    url = sr.get("url", "")
                    if not url:
                        continue

                    # Classify the URL
                    platform_name = self._classify_url(url)
                    if platform_name:
                        # This is a known platform — create a finding
                        results.append(
                            self._make_search_result(
                                username=username,
                                url=url,
                                platform_name=platform_name,
                                title=sr.get("title", ""),
                                snippet=sr.get("snippet", ""),
                                query_description=description,
                                investigation_id=investigation_id,
                            )
                        )

                # Rate limit between searches
                await asyncio.sleep(1.0)

        return results

    def _build_search_queries(self, username: str, variations: list[str]) -> list[dict[str, str]]:
        """Build search queries for web discovery."""
        queries = []

        # 1. Direct username search across platforms
        queries.append(
            {
                "query": f'"{username}" profile OR account OR portfolio OR about',
                "description": "General profile search",
            }
        )

        # 2. Username on specific platforms
        platform_sites = [
            "linkedin.com",
            "github.com",
            "twitter.com",
            "x.com",
            "instagram.com",
            "medium.com",
            "dev.to",
            "stackoverflow.com",
            "reddit.com",
            "youtube.com",
            "behance.net",
            "dribbble.com",
        ]
        for site in platform_sites:
            queries.append(
                {
                    "query": f'site:{site} "{username}"',
                    "description": f"{site} profile",
                }
            )

        # 3. Username variations
        for var in variations[:3]:
            if var != username:
                queries.append(
                    {
                        "query": f'"{var}" profile OR portfolio OR about',
                        "description": f'Variation "{var}"',
                    }
                )

        # 4. If username has parts, search as a name
        parts = re.split(r"[._\-\s]+", username)
        if len(parts) > 1:
            name_query = " ".join(parts)
            queries.append(
                {
                    "query": f'"{name_query}" site:linkedin.com',
                    "description": f'LinkedIn for "{name_query}"',
                }
            )
            queries.append(
                {
                    "query": f'"{name_query}" portfolio OR website OR blog',
                    "description": f'Personal site for "{name_query}"',
                }
            )

        # 5. Domain patterns
        if len(parts) > 1:
            fname, lname = parts[0], parts[-1]
            queries.append(
                {
                    "query": (
                        f"site:{fname}{lname}.dev OR site:{fname}.{lname}.dev "
                        f"OR site:{lname}{fname}.dev"
                    ),
                    "description": "Personal domain patterns",
                }
            )

        return queries

    async def _ddg_search(self, client: httpx.AsyncClient, query: str) -> list[dict[str, str]]:
        """Execute DuckDuckGo search with fallback chain."""
        # Try HTML endpoint first
        results = await self._try_ddg_html(client, query)
        if results:
            return results

        # Fallback to Lite
        results = await self._try_ddg_lite(client, query)
        if results:
            return results

        # Fallback to API
        results = await self._try_ddg_api(client, query)
        return results

    async def _try_ddg_html(self, client: httpx.AsyncClient, query: str) -> list[dict[str, str]]:
        """Try DuckDuckGo HTML endpoint."""
        try:
            response = await client.post(
                DDG_HTML_URL,
                data={"q": query, "b": ""},
                headers={
                    "User-Agent": _USER_AGENT,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            if response.status_code == 200:
                return self._parse_ddg_html(response.text)
        except Exception as exc:
            logger.debug("DDG HTML failed: %s", exc)
        return []

    async def _try_ddg_lite(self, client: httpx.AsyncClient, query: str) -> list[dict[str, str]]:
        """Try DuckDuckGo Lite endpoint."""
        try:
            response = await client.post(
                DDG_LITE_URL,
                data={"q": query},
                headers={
                    "User-Agent": _USER_AGENT,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            if response.status_code == 200:
                return self._parse_ddg_lite(response.text)
        except Exception as exc:
            logger.debug("DDG Lite failed: %s", exc)
        return []

    async def _try_ddg_api(self, client: httpx.AsyncClient, query: str) -> list[dict[str, str]]:
        """Try DuckDuckGo Instant Answer API."""
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
            )
            if response.status_code == 200:
                return self._parse_ddg_api(response.json())
        except Exception as exc:
            logger.debug("DDG API failed: %s", exc)
        return []

    def _parse_ddg_html(self, html: str) -> list[dict[str, str]]:
        """Parse DuckDuckGo HTML search results."""
        results = []
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

                # Extract actual URL from DDG redirect
                if "uddg=" in href:
                    match = re.search(r"uddg=([^&]+)", href)
                    if match:
                        url = unquote(match.group(1))

                if url:
                    results.append(
                        {
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                        }
                    )
        except Exception as exc:
            logger.debug("Failed to parse DDG HTML: %s", exc)
        return results[:10]

    def _parse_ddg_lite(self, html: str) -> list[dict[str, str]]:
        """Parse DuckDuckGo Lite results."""
        results = []
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

                if title and url:
                    results.append(
                        {
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                        }
                    )
        except Exception as exc:
            logger.debug("Failed to parse DDG Lite: %s", exc)
        return results[:10]

    def _parse_ddg_api(self, data: dict) -> list[dict[str, str]]:
        """Parse DuckDuckGo Instant Answer API JSON."""
        results = []

        if data.get("Abstract"):
            results.append(
                {
                    "title": data.get("Heading", ""),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("Abstract", ""),
                }
            )

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

    def _classify_url(self, url: str) -> str | None:
        """Classify a URL to a platform name. Returns None if not a known platform."""
        try:
            parsed = urlparse(url)
            host = parsed.hostname or ""
            # Check with and without www
            for domain, name in _PLATFORM_DOMAINS.items():
                if host == domain or host == f"www.{domain}":
                    return name
        except Exception:
            pass
        return None

    def _make_search_result(
        self,
        username: str,
        url: str,
        platform_name: str,
        title: str,
        snippet: str,
        query_description: str,
        investigation_id: str,
    ) -> RawResult:
        """Create a RawResult from a web search finding."""
        return RawResult(
            collector_name=self.COLLECTOR_NAME,
            collector_version=self.COLLECTOR_VERSION,
            target=username,
            target_type=TargetType.USERNAME,
            query=f"websearch:{platform_name.lower()}:{username}",
            status=ObservationStatus.SUCCESS,
            raw_response={
                "found": True,
                "platform": platform_name,
                "platform_key": platform_name.lower().replace("/", "").replace(".", ""),
                "username": username,
                "url": url,
                "status_code": 200,
                "evidence": {
                    "source": "web_search",
                    "title": title,
                    "snippet": snippet,
                    "query": query_description,
                },
                "profile": {
                    "name": username,
                    "platform": platform_name,
                    "url": url,
                    "title": title,
                    "snippet": snippet,
                },
            },
            normalized_value=username,
            confidence=0.85,
            metadata={
                "engine": "username_probe",
                "phase": "web_search",
                "platform_key": platform_name.lower().replace("/", "").replace(".", ""),
                "platform_name": platform_name,
            },
        )

    # ── Phase 2: Personal Domain Probing ─────────────────────────────────────

    async def _domain_probing_phase(
        self,
        username: str,
        variations: list[str],
        investigation_id: str,
    ) -> list[RawResult]:
        """Try common personal domain patterns."""
        results: list[RawResult] = []
        domains_to_try = self._generate_domain_patterns(username, variations)

        async with httpx.AsyncClient(
            timeout=5.0,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            for domain in domains_to_try:
                if self._requests_made >= self.budget.max_total_requests:
                    break

                url = f"https://{domain}"
                try:
                    self._requests_made += 1
                    response = await client.get(url)

                    if response.status_code == 200:
                        body = response.text.lower()
                        # Check it's not a parked domain or registrar page
                        parked_indicators = [
                            "domain for sale",
                            "buy this domain",
                            "parked",
                            "coming soon",
                            "under construction",
                            "godaddy",
                            "namecheap",
                            "hover.com",
                        ]
                        is_parked = any(ind in body for ind in parked_indicators)
                        if not is_parked and len(body) > 500:
                            # Looks like a real personal site
                            title = ""
                            try:
                                soup = BeautifulSoup(response.text, "html.parser")
                                title_el = soup.find("title")
                                if title_el:
                                    title = title_el.get_text(strip=True)[:100]
                            except Exception:
                                pass

                            results.append(
                                self._make_domain_result(
                                    username=username,
                                    url=url,
                                    domain=domain,
                                    title=title,
                                    investigation_id=investigation_id,
                                )
                            )

                except (httpx.TimeoutException, httpx.RequestError):
                    pass

                await asyncio.sleep(0.3)

        return results

    def _generate_domain_patterns(self, username: str, variations: list[str]) -> list[str]:
        """Generate personal domain patterns to try."""
        domains = []
        parts = re.split(r"[._\-\s]+", username)
        clean = re.sub(r"[^a-z0-9]", "", username.lower())

        tlds = [".dev", ".io", ".com", ".me", ".xyz", ".site", ".app"]

        if len(parts) >= 2:
            fname = parts[0].lower()
            lname = parts[-1].lower()
            fname_clean = re.sub(r"[^a-z]", "", fname)
            lname_clean = re.sub(r"[^a-z]", "", lname)

            if fname_clean and lname_clean:
                # firstname-lastname patterns
                for sep in ["", "-"]:
                    for tld in tlds:
                        domains.append(f"{fname_clean}{sep}{lname_clean}{tld}")
                # lastname-firstname
                for sep in ["", "-"]:
                    for tld in tlds:
                        domains.append(f"{lname_clean}{sep}{fname_clean}{tld}")
                # first initial + lastname
                for tld in tlds:
                    domains.append(f"{fname_clean[0]}{lname_clean}{tld}")
                # firstname + last initial
                for tld in tlds:
                    domains.append(f"{fname_clean}{lname_clean[0]}{tld}")

        # Full username as domain
        for tld in tlds:
            domains.append(f"{clean}{tld}")

        # variations as domains
        for var in variations[:3]:
            var_clean = re.sub(r"[^a-z0-9]", "", var.lower())
            if var_clean and var_clean != clean:
                for tld in tlds[:3]:
                    domains.append(f"{var_clean}{tld}")

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for d in domains:
            if d not in seen:
                seen.add(d)
                unique.append(d)

        return unique

    def _make_domain_result(
        self,
        username: str,
        url: str,
        domain: str,
        title: str,
        investigation_id: str,
    ) -> RawResult:
        """Create a RawResult from a domain finding."""
        return RawResult(
            collector_name=self.COLLECTOR_NAME,
            collector_version=self.COLLECTOR_VERSION,
            target=username,
            target_type=TargetType.USERNAME,
            query=f"domain:{domain}",
            status=ObservationStatus.SUCCESS,
            raw_response={
                "found": True,
                "platform": "Personal Website",
                "platform_key": "personal_website",
                "username": username,
                "url": url,
                "domain": domain,
                "status_code": 200,
                "evidence": {
                    "source": "domain_probe",
                    "title": title,
                    "domain": domain,
                },
                "profile": {
                    "name": username,
                    "platform": "Personal Website",
                    "url": url,
                    "title": title,
                    "domain": domain,
                },
            },
            normalized_value=username,
            confidence=0.75,
            metadata={
                "engine": "username_probe",
                "phase": "domain_probe",
                "platform_key": "personal_website",
                "platform_name": "Personal Website",
                "domain": domain,
            },
        )

    # ── Phase 3: Platform Probing ────────────────────────────────────────────

    async def _platform_probing_phase(
        self,
        username: str,
        variations: list[str],
        investigation_id: str,
        max_platforms: int | None = None,
    ) -> list[RawResult]:
        """Probe platforms: direct HTTP for enabled, adapter chain for disabled."""
        results: list[RawResult] = []
        seen_urls: set[str] = set()

        # ── Part A: Existing direct HTTP probing for enabled platforms ──
        enabled = get_enabled_platforms(self._platforms)
        platform_limit = max_platforms or self.budget.max_platforms
        enabled = enabled[:platform_limit]

        if enabled:
            enabled_variations = variations[: self.budget.max_variations]
            tasks = []

            for platform in enabled:
                for variant in enabled_variations:
                    if self._requests_made >= self.budget.max_total_requests:
                        break
                    tasks.append(self._probe_single(platform, variant, username, investigation_id))

            semaphore = asyncio.Semaphore(min(5, len(enabled)))

            async def _bounded(coro: Any) -> ProbeResult | None:
                async with semaphore:
                    return await coro

            probe_results = await asyncio.gather(
                *[_bounded(t) for t in tasks],
                return_exceptions=True,
            )

            for r in probe_results:
                if isinstance(r, ProbeResult) and r.found:
                    raw = self._to_raw_result(r, investigation_id)
                    url = raw.raw_response.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        results.append(raw)

        # ── Part B: Intelligence adapter probing for disabled platforms ──
        all_platforms = load_platforms()
        disabled = [p for p in all_platforms.values() if not p.enabled]

        if disabled and self._requests_made < self.budget.max_total_requests:
            intelligence_variations = variations[: self.budget.max_variations]
            intel_results = await self._intelligence.probe_all_platforms(
                username,
                intelligence_variations,
                investigation_id,
                self.budget,
                max_platforms=len(disabled),
            )
            for raw in intel_results:
                url = raw.raw_response.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    results.append(raw)

        return results

    async def _probe_single(
        self,
        platform: PlatformDefinition,
        username: str,
        original_username: str,
        investigation_id: str,
    ) -> ProbeResult | None:
        """Probe a single platform for a single username variant."""
        if self._requests_made >= self.budget.max_total_requests:
            return None

        url = platform.url_pattern.replace("{username}", username)

        limiter = self._get_rate_limiter(platform)
        await limiter.acquire()

        self._requests_made += 1

        try:
            async with httpx.AsyncClient(
                timeout=platform.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "OSINT-Nexus/1.0 (research; username-investigation)",
                    "Accept": "text/html,application/xhtml+xml,*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as client:
                response = await client.request(platform.method, url)
                return self._classify_response(platform, username, original_username, url, response)

        except httpx.TimeoutException:
            return ProbeResult(
                platform_key=platform.key,
                platform_name=platform.name,
                username=username,
                url=url,
                found=False,
                error="timeout",
            )
        except httpx.RequestError as exc:
            return ProbeResult(
                platform_key=platform.key,
                platform_name=platform.name,
                username=username,
                url=url,
                found=False,
                error=str(exc),
            )

    def _classify_response(
        self,
        platform: PlatformDefinition,
        username: str,
        original_username: str,
        url: str,
        response: httpx.Response,
    ) -> ProbeResult:
        """Classify an HTTP response using platform-specific indicators."""
        status = response.status_code
        body = response.text.lower()
        indicators = platform.success_indicators
        failure = platform.failure_indicators

        # Check failure indicators first
        fail_codes = failure.get("status_codes", [])
        if status in fail_codes:
            return ProbeResult(
                platform_key=platform.key,
                platform_name=platform.name,
                username=username,
                url=url,
                found=False,
                status_code=status,
            )

        fail_body = failure.get("body_contains", [])
        for term in fail_body:
            if term.lower() in body:
                return ProbeResult(
                    platform_key=platform.key,
                    platform_name=platform.name,
                    username=username,
                    url=url,
                    found=False,
                    status_code=status,
                )

        # Check success indicators
        ok_codes = indicators.get("status_codes", [200])
        if status not in ok_codes:
            return ProbeResult(
                platform_key=platform.key,
                platform_name=platform.name,
                username=username,
                url=url,
                found=False,
                status_code=status,
            )

        body_must_have = indicators.get("body_contains", [])
        for term in body_must_have:
            if term.lower() not in body:
                return ProbeResult(
                    platform_key=platform.key,
                    platform_name=platform.name,
                    username=username,
                    url=url,
                    found=False,
                    status_code=status,
                    confidence=0.3,
                    evidence={"reason": f"body missing required term: {term}"},
                )

        body_must_not_have = indicators.get("body_not_contains", [])
        for term in body_must_not_have:
            if term.lower() in body:
                return ProbeResult(
                    platform_key=platform.key,
                    platform_name=platform.name,
                    username=username,
                    url=url,
                    found=False,
                    status_code=status,
                    confidence=0.3,
                    evidence={"reason": f"body contains negative term: {term}"},
                )

        confidence = self._compute_confidence(platform, status, body)

        return ProbeResult(
            platform_key=platform.key,
            platform_name=platform.name,
            username=username,
            url=url,
            found=True,
            status_code=status,
            confidence=confidence,
            evidence={
                "status_code": status,
                "url_final": str(response.url),
                "content_type": response.headers.get("content-type", ""),
            },
        )

    def _compute_confidence(
        self,
        platform: PlatformDefinition,
        status: int,
        body: str,
    ) -> float:
        """Compute confidence score for a positive finding."""
        confidence = 0.7

        if status == 200:
            confidence += 0.1

        if len(body) > 10000:
            confidence += 0.05

        if platform.success_indicators.get("body_not_contains"):
            confidence += 0.05

        return min(confidence, 0.95)

    def _to_raw_result(
        self,
        probe: ProbeResult,
        investigation_id: str,
    ) -> RawResult:
        """Convert a ProbeResult to a RawResult."""
        return RawResult(
            collector_name=self.COLLECTOR_NAME,
            collector_version=self.COLLECTOR_VERSION,
            target=probe.username,
            target_type=TargetType.USERNAME,
            query=f"probe:{probe.platform_key}:{probe.username}",
            status=ObservationStatus.SUCCESS,
            raw_response={
                "found": True,
                "platform": probe.platform_name,
                "platform_key": probe.platform_key,
                "username": probe.username,
                "url": probe.url,
                "status_code": probe.status_code,
                "evidence": probe.evidence,
                "profile": {
                    "name": probe.username,
                    "platform": probe.platform_name,
                    "url": probe.url,
                },
            },
            normalized_value=probe.username,
            confidence=probe.confidence,
            metadata={
                "engine": "username_probe",
                "phase": "platform_probe",
                "platform_key": probe.platform_key,
                "platform_name": probe.platform_name,
            },
        )

    def _get_rate_limiter(self, platform: PlatformDefinition) -> TokenBucketRateLimiter:
        """Get or create a rate limiter for a platform."""
        if platform.key not in self._rate_limiters:
            rpm = platform.rate_limit_rpm
            self._rate_limiters[platform.key] = TokenBucketRateLimiter(
                rate=rpm / 60.0,
                burst=min(rpm, 10),
            )
        return self._rate_limiters[platform.key]
