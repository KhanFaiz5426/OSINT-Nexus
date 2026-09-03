"""HTTP collector — Analyze HTTP responses for metadata and technologies.

Performs HEAD/GET requests to capture headers, page title, redirects,
technologies, and cookie attributes. Polite rate limiting (5 req/s).
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import OSINTCollector
from app.core.config import get_settings
from app.models import ObservationStatus, RawResult, TargetType

logger = logging.getLogger(__name__)

# Technology detection patterns (header -> technology name)
TECHNOLOGY_HEADERS = {
    "x-powered-by": {
        "php": "PHP",
        "asp.net": "ASP.NET",
        "express": "Express.js",
        "next.js": "Next.js",
        "rails": "Ruby on Rails",
        "django": "Django",
        "laravel": "Laravel",
    },
    "server": {
        "nginx": "Nginx",
        "apache": "Apache",
        "cloudflare": "Cloudflare",
        "microsoft-iis": "Microsoft IIS",
        "openresty": "OpenResty",
        "lighttpd": "Lighttpd",
        "caddy": "Caddy",
    },
    "x-aspnet-version": {"x-aspnet-version": "ASP.NET"},
    "x-generator": {
        "wordpress": "WordPress",
        "drupal": "Drupal",
        "joomla": "Joomla",
    },
}

# Cookie-based technology detection
COOKIE_PATTERNS = {
    "PHPSESSID": "PHP",
    "JSESSIONID": "Java",
    "connect.sid": "Express.js",
    "_rails_session": "Ruby on Rails",
    "csrftoken": "Django",
    "XSRF-TOKEN": "Laravel/Vue",
}


class HTTPCollector(OSINTCollector):
    """HTTP metadata and technology collector."""

    name = "http"
    version = "1.0.0"
    supported_target_types = [TargetType.DOMAIN, TargetType.URL]
    requires_api_key = False
    cache_ttl = 3600  # 1 hour
    rate_limit_rpm = 300  # 5 req/s

    async def _collect(self, target: str, target_type: TargetType) -> RawResult:
        settings = get_settings()

        # Build URL
        url = target
        if target_type == TargetType.DOMAIN:
            url = f"https://{target}"

        try:
            async with httpx.AsyncClient(
                timeout=settings.HTTP_TIMEOUT,
                follow_redirects=True,
                max_redirects=5,
            ) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; OSINT-Nexus/1.0; research)",
                        "Accept": "text/html,application/xhtml+xml,*/*",
                    },
                )

                # Parse response
                headers_dict = dict(response.headers)
                title = self._extract_title(response.text)
                technologies = self._detect_technologies(headers_dict, response.cookies)
                redirects = [
                    {"url": str(r.url), "status": r.status_code}
                    for r in response.history
                ]
                cookies = [
                    {
                        "name": c.name,
                        "domain": c.domain,
                        "secure": c.secure,
                        "httponly": c.has_nonstandard_attr("httponly"),
                    }
                    for c in response.cookies.jar
                ]

                raw_response = {
                    "url": str(response.url),
                    "status_code": response.status_code,
                    "headers": headers_dict,
                    "title": title,
                    "technologies": technologies,
                    "redirects": redirects,
                    "cookies": cookies,
                    "content_type": headers_dict.get("content-type", ""),
                    "content_length": len(response.content),
                }

                return RawResult(
                    collector_name=self.name,
                    collector_version=self.version,
                    target=target,
                    target_type=target_type,
                    query=f"http:{url}",
                    status=ObservationStatus.SUCCESS,
                    raw_response=raw_response,
                    normalized_value=str(response.url),
                    confidence=0.9,
                    metadata={
                        "status_code": response.status_code,
                        "technologies_count": len(technologies),
                        "redirect_count": len(redirects),
                    },
                )

        except httpx.TimeoutException:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"http:{url}",
                status=ObservationStatus.TIMEOUT,
                error_message=f"HTTP request timed out after {settings.HTTP_TIMEOUT}s",
            )
        except httpx.ConnectError as exc:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"http:{url}",
                status=ObservationStatus.ERROR,
                error_message=f"Connection failed: {exc}",
            )
        except Exception as exc:
            return RawResult(
                collector_name=self.name,
                collector_version=self.version,
                target=target,
                target_type=target_type,
                query=f"http:{url}",
                status=ObservationStatus.ERROR,
                error_message=f"HTTP collection failed: {exc}",
            )

    def _extract_title(self, html: str) -> str:
        """Extract <title> from HTML content."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                return title_tag.string.strip()
        except Exception:
            pass
        return ""

    def _detect_technologies(
        self, headers: dict[str, Any], cookies: Any
    ) -> list[dict[str, str]]:
        """Detect technologies from response headers and cookies."""
        detected: list[dict[str, str]] = []

        # Check headers
        for header_name, patterns in TECHNOLOGY_HEADERS.items():
            header_value = headers.get(header_name, "").lower()
            if header_value:
                for pattern, tech_name in patterns.items():
                    if pattern in header_value:
                        detected.append({
                            "name": tech_name,
                            "source": f"header:{header_name}",
                            "version": self._extract_version(header_value),
                        })

        # Check cookies
        for cookie in cookies:
            cookie_name = getattr(cookie, "name", str(cookie))
            for pattern, tech_name in COOKIE_PATTERNS.items():
                if cookie_name == pattern:
                    detected.append({
                        "name": tech_name,
                        "source": "cookie",
                        "version": "",
                    })

        return detected

    def _extract_version(self, value: str) -> str:
        """Extract version string from a header value."""
        match = re.search(r"[\d]+\.[\d]+(?:\.[\d]+)?", value)
        return match.group(0) if match else ""
