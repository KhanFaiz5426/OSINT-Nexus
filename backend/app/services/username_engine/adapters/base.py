"""Platform Intelligence Adapter — abstract interface for platform-specific acquisition.

Each adapter implements a single acquisition strategy:
- DirectHTTPAdapter: simple HTTP probe (existing behavior)
- APIAdapter: official platform API (YouTube, GitHub REST, etc.)
- SearchDiscoveryAdapter: web search to discover profile URLs

Adapters are stateless and idempotent. The orchestrator decides which
adapters to try and in what order.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.models import RawResult, TargetType


class AcquisitionMethod(StrEnum):
    """How the adapter acquired intelligence about a platform."""

    DIRECT_HTTP = "direct_http"
    API = "api"
    SEARCH_DISCOVERY = "search_discovery"
    BROWSER = "browser"  # reserved, not used yet


class EvidenceConfidence(StrEnum):
    """How confident we are that the evidence is authentic.

    LOW: search engine said the URL exists (could be stale/wrong)
    MEDIUM: direct HTTP probe matched success indicators
    HIGH: official API returned structured profile data
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class AdapterResult:
    """Result from a single adapter probing a platform for a username."""

    platform_key: str
    platform_name: str
    username: str
    found: bool
    url: str = ""
    acquisition_method: AcquisitionMethod = AcquisitionMethod.DIRECT_HTTP
    confidence: float = 0.0
    evidence_confidence: EvidenceConfidence = EvidenceConfidence.MEDIUM
    evidence: dict[str, Any] = field(default_factory=dict)
    profile: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    status_code: int = 0


class PlatformAdapter(abc.ABC):
    """Abstract base for platform intelligence adapters.

    Subclasses implement ``probe()`` to check whether a username exists
    on a specific platform using a specific acquisition method.

    Adapters must:
    - Never raise exceptions from ``probe()`` — return error in AdapterResult
    - Return empty results when credentials are missing (not exceptions)
    - Set ``acquisition_method`` and ``evidence_confidence`` on every result
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique identifier for this adapter (e.g. 'youtube_api')."""

    @property
    @abc.abstractmethod
    def acquisition_method(self) -> AcquisitionMethod:
        """How this adapter acquires intelligence."""

    @property
    @abc.abstractmethod
    def supported_platforms(self) -> list[str]:
        """Platform keys this adapter can handle (e.g. ['youtube'])."""

    @abc.abstractmethod
    async def probe(
        self,
        platform_key: str,
        username: str,
        investigation_id: str,
    ) -> AdapterResult | None:
        """Probe a platform for a username.

        Returns:
            AdapterResult if the adapter handled this platform,
            None if the adapter cannot handle this platform (skip).
        """

    @property
    def is_available(self) -> bool:
        """Whether this adapter is ready to use (API key present, etc.)."""
        return True

    def to_raw_result(
        self,
        result: AdapterResult,
        investigation_id: str,
    ) -> RawResult:
        """Convert an AdapterResult to a RawResult for the pipeline."""
        from app.models import ObservationStatus

        status = (
            ObservationStatus.SUCCESS if result.found else ObservationStatus.SUCCESS
        )

        return RawResult(
            collector_name="username_probe",
            collector_version="3.0.0",
            target=result.username,
            target_type=TargetType.USERNAME,
            query=f"{result.acquisition_method.value}:{result.platform_key}:{result.username}",
            status=status,
            raw_response={
                "found": result.found,
                "platform": result.platform_name,
                "platform_key": result.platform_key,
                "username": result.username,
                "url": result.url,
                "status_code": result.status_code,
                "acquisition_method": result.acquisition_method.value,
                "evidence_confidence": result.evidence_confidence.value,
                "evidence": result.evidence,
                "profile": result.profile,
            },
            normalized_value=result.username,
            confidence=result.confidence,
            metadata={
                "engine": "username_probe",
                "phase": "platform_intelligence",
                "adapter": self.name,
                "acquisition_method": result.acquisition_method.value,
                "evidence_confidence": result.evidence_confidence.value,
                "platform_key": result.platform_key,
                "platform_name": result.platform_name,
            },
        )
