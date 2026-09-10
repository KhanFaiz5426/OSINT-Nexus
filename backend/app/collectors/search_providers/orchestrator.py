"""Multi-provider search orchestrator.

Runs enabled SearchProvider instances concurrently, collects results,
deduplicates by URL, and produces a merged ranked result list. Individual
provider failures do not prevent other providers from succeeding.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from app.collectors.search_providers.base import (
    ProviderStatus,
    ProviderStatusCode,
    SearchProvider,
    SearchProviderResponse,
    SearchRequest,
    SearchResult,
)

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorResult:
    """Merged output from all providers."""

    results: list[SearchResult] = field(default_factory=list)
    provider_statuses: list[ProviderStatus] = field(default_factory=list)
    total_raw_results: int = 0
    deduplicated_count: int = 0


class MultiProviderOrchestrator:
    """Runs multiple SearchProviders concurrently and merges results.

    Usage::

        orch = MultiProviderOrchestrator([ddg_provider, searxng_provider])
        merged = await orch.search(SearchRequest(query="example.com"))
    """

    def __init__(self, providers: list[SearchProvider]) -> None:
        self._providers = providers

    @property
    def provider_names(self) -> list[str]:
        return [p.name for p in self._providers]

    async def search(self, request: SearchRequest) -> OrchestratorResult:
        """Execute search across all providers concurrently."""
        if not self._providers:
            return OrchestratorResult()

        # Run all providers concurrently with per-provider timeout
        tasks = [
            asyncio.wait_for(
                provider.search(request),
                timeout=request.timeout + 2.0,  # small grace period beyond provider timeout
            )
            for provider in self._providers
        ]

        raw_responses: list[SearchProviderResponse | BaseException] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        # Collect results and statuses
        all_results: list[SearchResult] = []
        statuses: list[ProviderStatus] = []

        for provider, response in zip(self._providers, raw_responses, strict=False):
            if isinstance(response, BaseException):
                logger.warning("Provider %s raised exception: %s", provider.name, response)
                statuses.append(
                    ProviderStatus(
                        provider_name=provider.name,
                        status=ProviderStatusCode.ERROR,
                        error_message=str(response),
                    )
                )
                continue

            statuses.append(response.status)
            all_results.extend(response.results)

        total_raw = len(all_results)

        # Deduplicate by normalized URL
        deduped = _deduplicate_results(all_results)

        # Rank: interleave from providers, preserving original rank within each
        ranked = _interleave_rank(deduped, [p.name for p in self._providers])

        return OrchestratorResult(
            results=ranked,
            provider_statuses=statuses,
            total_raw_results=total_raw,
            deduplicated_count=total_raw - len(ranked),
        )


def _deduplicate_results(results: list[SearchResult]) -> list[SearchResult]:
    """Remove duplicate URLs, keeping the first occurrence (higher priority)."""
    seen: set[str] = set()
    deduped: list[SearchResult] = []

    for r in results:
        norm = r.normalized_url()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        deduped.append(r)

    return deduped


def _interleave_rank(results: list[SearchResult], provider_order: list[str]) -> list[SearchResult]:
    """Interleave results from multiple providers for balanced ranking.

    Within each provider, results retain their original rank order.
    The interleaving alternates: provider-1 rank-0, provider-2 rank-0,
    provider-1 rank-1, provider-2 rank-1, etc.
    """
    if not results:
        return []

    # Group by provider, preserving rank order
    by_provider: dict[str, list[SearchResult]] = {name: [] for name in provider_order}
    for r in results:
        if r.provider in by_provider:
            by_provider[r.provider].append(r)
        else:
            # Unknown provider — append at end
            by_provider.setdefault(r.provider, []).append(r)

    # Interleave
    interleaved: list[SearchResult] = []
    max_len = max((len(v) for v in by_provider.values()), default=0)

    for i in range(max_len):
        for name in provider_order:
            bucket = by_provider.get(name, [])
            if i < len(bucket):
                interleaved.append(bucket[i])

    return interleaved
