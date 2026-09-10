"""Platform Intelligence Orchestrator — routes platforms to appropriate adapters.

Replaces the disabled-platform logic in UsernameProbeEngine. For each
platform, selects the best available adapter based on priority:

1. API adapter (highest confidence, structured data)
2. Direct HTTP adapter (reliable for simple platforms)
3. Search discovery adapter (fallback for complex platforms)

Falls back gracefully: if an adapter is unavailable or returns an error,
the next adapter in the priority chain is tried.

Integrates with the existing probe engine via ``integrate_with_probe_engine()``
which replaces the platform probing phase.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.models import RawResult
from app.services.username_engine.adapters.base import (
    AdapterResult,
    PlatformAdapter,
)
from app.services.username_engine.adapters.http_adapter import DirectHTTPAdapter
from app.services.username_engine.adapters.search_discovery_adapter import (
    SearchDiscoveryAdapter,
)
from app.services.username_engine.adapters.youtube_api_adapter import YouTubeAPIAdapter
from app.services.username_engine.models import ProbeBudget
from app.services.username_engine.platform_store import (
    get_enabled_platforms,
    load_platforms,
)

logger = logging.getLogger(__name__)


# Default adapter priority: API > HTTP > Search Discovery
_DEFAULT_ADAPTER_PRIORITY: list[str] = [
    "youtube_api",
    "direct_http",
    "search_discovery",
]

# Platform-to-adapter routing overrides
# Platforms not listed here use the default priority chain
_PLATFORM_ADAPTER_OVERRIDES: dict[str, list[str]] = {
    # YouTube: prefer API, fallback to search discovery (skip direct HTTP)
    "youtube": ["youtube_api", "search_discovery"],
    # X/Twitter: search discovery only (direct HTTP unreliable)
    "x_twitter": ["search_discovery"],
    # LinkedIn: search discovery only
    "linkedin": ["search_discovery"],
    # Instagram: search discovery only
    "instagram": ["search_discovery"],
    # TikTok: search discovery only
    "tiktok": ["search_discovery"],
}


class PlatformIntelligenceOrchestrator:
    """Routes platform probing through appropriate adapters.

    Manages adapter lifecycle and applies platform-specific routing.
    Integrates with UsernameProbeEngine to replace the platform probing
    phase for platforms that need non-HTTP acquisition.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, PlatformAdapter] = {}
        self._platforms = load_platforms()
        self._register_adapters()

    def _register_adapters(self) -> None:
        """Register all built-in adapters."""
        adapters = [
            DirectHTTPAdapter(),
            YouTubeAPIAdapter(),
            SearchDiscoveryAdapter(),
        ]
        for adapter in adapters:
            self._adapters[adapter.name] = adapter
            logger.info(
                "Registered adapter: %s (method=%s, available=%s)",
                adapter.name,
                adapter.acquisition_method,
                adapter.is_available,
            )

    def get_adapter_chain(self, platform_key: str) -> list[PlatformAdapter]:
        """Get ordered list of adapters to try for a platform."""
        override = _PLATFORM_ADAPTER_OVERRIDES.get(platform_key)
        chain_names = override or _DEFAULT_ADAPTER_PRIORITY

        chain = []
        for name in chain_names:
            adapter = self._adapters.get(name)
            if adapter and adapter.is_available:
                chain.append(adapter)

        return chain

    async def probe_platform(
        self,
        platform_key: str,
        username: str,
        investigation_id: str,
        budget: ProbeBudget,
    ) -> AdapterResult | None:
        """Probe a single platform using the adapter chain.

        Tries adapters in priority order. Returns the first successful
        result, or None if all adapters fail.
        """
        chain = self.get_adapter_chain(platform_key)
        platform_def = self._platforms.get(platform_key)

        for adapter in chain:
            # For DirectHTTPAdapter, pass the platform definition
            kwargs: dict[str, Any] = {}
            if isinstance(adapter, DirectHTTPAdapter):
                kwargs["platform"] = platform_def

            try:
                result = await adapter.probe(platform_key, username, investigation_id, **kwargs)
                if result is not None:
                    if result.found:
                        logger.info(
                            "Found %s on %s via %s (confidence=%.2f)",
                            username,
                            platform_key,
                            adapter.name,
                            result.confidence,
                        )
                    else:
                        logger.debug(
                            "Not found %s on %s via %s",
                            username,
                            platform_key,
                            adapter.name,
                        )
                    return result
            except Exception as exc:
                logger.warning(
                    "Adapter %s failed for %s on %s: %s",
                    adapter.name,
                    username,
                    platform_key,
                    exc,
                )
                continue

        return None

    async def probe_all_platforms(
        self,
        username: str,
        variations: list[str],
        investigation_id: str,
        budget: ProbeBudget,
        max_platforms: int | None = None,
    ) -> list[RawResult]:
        """Probe all enabled platforms, using adapters as appropriate.

        This is the main entry point that replaces UsernameProbeEngine's
        platform probing phase.
        """
        enabled = get_enabled_platforms(self._platforms)
        platform_limit = max_platforms or budget.max_platforms
        enabled = enabled[:platform_limit]

        if not enabled:
            return []

        results: list[RawResult] = []
        seen_urls: set[str] = set()
        variations = variations[: budget.max_variations]

        # Build tasks: each platform x each variation
        tasks = []
        for platform in enabled:
            for variant in variations:
                tasks.append(
                    self._probe_single_with_adapter(
                        platform.key, variant, username, investigation_id, budget
                    )
                )

        # Run with concurrency limit
        semaphore = asyncio.Semaphore(min(5, len(enabled)))

        async def _bounded(coro: Any) -> AdapterResult | None:
            async with semaphore:
                return await coro

        probe_results = await asyncio.gather(
            *[_bounded(t) for t in tasks],
            return_exceptions=True,
        )

        for r in probe_results:
            if isinstance(r, AdapterResult) and r.found:
                url = r.url or r.profile.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    adapter = self._adapters.get("direct_http")
                    if adapter:
                        results.append(adapter.to_raw_result(r, investigation_id))

        return results

    async def _probe_single_with_adapter(
        self,
        platform_key: str,
        username: str,
        original_username: str,
        investigation_id: str,
        budget: ProbeBudget,
    ) -> AdapterResult | None:
        """Probe a single platform with adapter chain, respecting budget."""
        return await self.probe_platform(platform_key, username, investigation_id, budget)

    def get_adapter_status(self) -> dict[str, Any]:
        """Return status of all registered adapters."""
        return {
            name: {
                "available": adapter.is_available,
                "method": adapter.acquisition_method,
                "platforms": adapter.supported_platforms,
            }
            for name, adapter in self._adapters.items()
        }
