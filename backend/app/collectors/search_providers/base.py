"""Search provider base — normalized types and abstract interface.

All search providers implement the SearchProvider protocol. Providers accept
a SearchRequest and return a SearchProviderResponse containing normalized
SearchResult objects. This abstraction is target-type agnostic: query
generation is the caller's responsibility.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ProviderStatusCode(StrEnum):
    """Outcome of a single provider's search execution."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    DISABLED = "disabled"


@dataclass(frozen=True)
class SearchRequest:
    """Normalized search request sent to every provider.

    Providers must not interpret the query semantically — they execute the
    search string as-is and return raw results.
    """

    query: str
    max_results: int = 10
    timeout: float = 10.0


@dataclass(frozen=True)
class SearchResult:
    """A single normalized search result from any provider."""

    title: str
    url: str
    snippet: str = ""
    provider: str = ""
    engine: str = ""
    rank: int = 0  # 0-based rank within the provider's results

    def normalized_url(self) -> str:
        """Return a lowered, trailing-slash-stripped URL for dedup."""
        return self.url.lower().rstrip("/")


@dataclass
class ProviderStatus:
    """Outcome metadata for a single provider execution."""

    provider_name: str
    status: ProviderStatusCode = ProviderStatusCode.SUCCESS
    result_count: int = 0
    error_message: str = ""
    elapsed_seconds: float = 0.0


@dataclass
class SearchProviderResponse:
    """Complete response from a single search provider."""

    provider_name: str
    results: list[SearchResult] = field(default_factory=list)
    status: ProviderStatus = field(default_factory=lambda: ProviderStatus(provider_name=""))

    def __post_init__(self) -> None:
        if not self.status.provider_name:
            self.status = ProviderStatus(provider_name=self.provider_name)


class SearchProvider(abc.ABC):
    """Abstract base for all search providers.

    Subclasses implement ``search()`` to execute a query against their
    backend and return normalized results. Providers must:
    - Never raise exceptions from ``search()`` — return error status instead
    - Respect ``request.timeout`` and ``request.max_results``
    - Set ``provider`` on every SearchResult they return
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique identifier for this provider."""

    @abc.abstractmethod
    async def search(self, request: SearchRequest) -> SearchProviderResponse:
        """Execute a search and return normalized results."""

    async def health_check(self) -> dict[str, Any]:
        """Return provider health information."""
        return {
            "provider": self.name,
            "available": True,
        }
