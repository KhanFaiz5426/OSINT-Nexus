"""Search providers — pluggable web search backends.

This package defines the SearchProvider interface and provides implementations
for DuckDuckGo and SearXNG. The multi-provider orchestrator runs enabled
providers concurrently and merges/deduplicates results.

Providers:
- DuckDuckGoProvider: HTML/Lite/API fallback chain (always available)
- SearXNGProvider: External SearXNG instance via HTTP JSON API (optional)
"""

from app.collectors.search_providers.base import (
    ProviderStatus,
    SearchProvider,
    SearchProviderResponse,
    SearchRequest,
    SearchResult,
)
from app.collectors.search_providers.duckduckgo import DuckDuckGoProvider
from app.collectors.search_providers.orchestrator import MultiProviderOrchestrator
from app.collectors.search_providers.searxng import SearXNGProvider

__all__ = [
    "DuckDuckGoProvider",
    "MultiProviderOrchestrator",
    "ProviderStatus",
    "SearchProvider",
    "SearchProviderResponse",
    "SearchRequest",
    "SearchResult",
    "SearXNGProvider",
]
