"""Direct HTTP adapter — wraps existing platform probing behavior.

This adapter preserves the current direct HTTP probe logic from
UsernameProbeEngine._probe_single(). It is the default adapter for
platforms where simple HTTP GET works reliably.
"""

from __future__ import annotations

import logging

import httpx

from app.services.username_engine.adapters.base import (
    AcquisitionMethod,
    AdapterResult,
    EvidenceConfidence,
    PlatformAdapter,
)
from app.services.username_engine.models import PlatformDefinition

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class DirectHTTPAdapter(PlatformAdapter):
    """Adapter that probes platforms via direct HTTP GET requests.

    This is the existing behavior extracted into the adapter interface.
    Used for GitHub, GitLab, Reddit, Twitch, Medium, etc.
    """

    @property
    def name(self) -> str:
        return "direct_http"

    @property
    def acquisition_method(self) -> AcquisitionMethod:
        return AcquisitionMethod.DIRECT_HTTP

    @property
    def supported_platforms(self) -> list[str]:
        # This adapter handles all platforms — the orchestrator decides
        # which ones to route here vs other adapters.
        return []

    async def probe(
        self,
        platform_key: str,
        username: str,
        investigation_id: str,
        *,
        platform: PlatformDefinition | None = None,
    ) -> AdapterResult | None:
        """Probe a platform via direct HTTP.

        Args:
            platform_key: Platform key from platforms.json
            username: Username to probe
            investigation_id: Owning investigation UUID
            platform: PlatformDefinition (required for this adapter)

        Returns:
            AdapterResult if platform is provided, None otherwise.
        """
        if platform is None:
            return None

        url = platform.url_pattern.replace("{username}", username)

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
                return self._classify_response(platform, username, url, response)

        except httpx.TimeoutException:
            return AdapterResult(
                platform_key=platform_key,
                platform_name=platform.name,
                username=username,
                found=False,
                url=url,
                acquisition_method=self.acquisition_method,
                error="timeout",
            )
        except httpx.RequestError as exc:
            return AdapterResult(
                platform_key=platform_key,
                platform_name=platform.name,
                username=username,
                found=False,
                url=url,
                acquisition_method=self.acquisition_method,
                error=str(exc),
            )

    def _classify_response(
        self,
        platform: PlatformDefinition,
        username: str,
        url: str,
        response: httpx.Response,
    ) -> AdapterResult:
        """Classify an HTTP response using platform-specific indicators."""
        status = response.status_code
        body = response.text.lower()
        indicators = platform.success_indicators
        failure = platform.failure_indicators

        # Check failure indicators first
        fail_codes = failure.get("status_codes", [])
        if status in fail_codes:
            return AdapterResult(
                platform_key=platform.key,
                platform_name=platform.name,
                username=username,
                found=False,
                url=url,
                acquisition_method=self.acquisition_method,
                status_code=status,
                evidence_confidence=EvidenceConfidence.MEDIUM,
            )

        fail_body = failure.get("body_contains", [])
        for term in fail_body:
            if term.lower() in body:
                return AdapterResult(
                    platform_key=platform.key,
                    platform_name=platform.name,
                    username=username,
                    found=False,
                    url=url,
                    acquisition_method=self.acquisition_method,
                    status_code=status,
                    evidence_confidence=EvidenceConfidence.MEDIUM,
                )

        # Check success indicators
        ok_codes = indicators.get("status_codes", [200])
        if status not in ok_codes:
            return AdapterResult(
                platform_key=platform.key,
                platform_name=platform.name,
                username=username,
                found=False,
                url=url,
                acquisition_method=self.acquisition_method,
                status_code=status,
                evidence_confidence=EvidenceConfidence.MEDIUM,
            )

        body_must_have = indicators.get("body_contains", [])
        for term in body_must_have:
            if term.lower() not in body:
                return AdapterResult(
                    platform_key=platform.key,
                    platform_name=platform.name,
                    username=username,
                    found=False,
                    url=url,
                    acquisition_method=self.acquisition_method,
                    status_code=status,
                    confidence=0.3,
                    evidence_confidence=EvidenceConfidence.MEDIUM,
                    evidence={"reason": f"body missing required term: {term}"},
                )

        body_must_not_have = indicators.get("body_not_contains", [])
        for term in body_must_not_have:
            if term.lower() in body:
                return AdapterResult(
                    platform_key=platform.key,
                    platform_name=platform.name,
                    username=username,
                    found=False,
                    url=url,
                    acquisition_method=self.acquisition_method,
                    status_code=status,
                    confidence=0.3,
                    evidence_confidence=EvidenceConfidence.MEDIUM,
                    evidence={"reason": f"body contains negative term: {term}"},
                )

        confidence = self._compute_confidence(platform, status, body)

        return AdapterResult(
            platform_key=platform.key,
            platform_name=platform.name,
            username=username,
            found=True,
            url=url,
            acquisition_method=self.acquisition_method,
            status_code=status,
            confidence=confidence,
            evidence_confidence=EvidenceConfidence.MEDIUM,
            evidence={
                "status_code": status,
                "url_final": str(response.url),
                "content_type": response.headers.get("content-type", ""),
            },
            profile={
                "name": username,
                "platform": platform.name,
                "url": url,
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
