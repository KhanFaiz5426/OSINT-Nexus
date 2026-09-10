"""Models for the Username Intelligence Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlatformDefinition:
    """A platform that can be probed for username existence."""

    key: str
    name: str
    url_pattern: str
    method: str = "GET"
    success_indicators: dict[str, Any] = field(default_factory=dict)
    failure_indicators: dict[str, Any] = field(default_factory=dict)
    rate_limit_rpm: int = 30
    timeout: float = 5.0
    enabled: bool = True
    notes: str = ""


@dataclass
class ProbeBudget:
    """Investigation-level budget for username probing.

    Hard upper bounds prevent accidental request explosions.
    """

    max_variations: int = 10
    max_platforms: int = 20
    max_total_requests: int = 200
    timeout: float = 5.0

    # Hard upper bounds (configurable values cannot exceed these)
    ABSOLUTE_MAX_VARIATIONS: int = 25
    ABSOLUTE_MAX_PLATFORMS: int = 50
    ABSOLUTE_MAX_REQUESTS: int = 1000

    def __post_init__(self) -> None:
        self.max_variations = min(self.max_variations, self.ABSOLUTE_MAX_VARIATIONS)
        self.max_platforms = min(self.max_platforms, self.ABSOLUTE_MAX_PLATFORMS)
        self.max_total_requests = min(self.max_total_requests, self.ABSOLUTE_MAX_REQUESTS)


@dataclass
class ProbeResult:
    """Result of probing a single platform for a single username."""

    platform_key: str
    platform_name: str
    username: str
    url: str
    found: bool
    status_code: int = 0
    confidence: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str = ""
