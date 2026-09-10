"""Tests for the search collector.

Tests the SearchCollector with mocked provider/orchestrator responses.
No live API calls are made.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.collectors.search_collector import SearchCollector
from app.collectors.search_providers.base import (
    ProviderStatus,
    ProviderStatusCode,
    SearchResult,
)
from app.collectors.search_providers.orchestrator import OrchestratorResult
from app.models import ObservationStatus, TargetType

# ── Mock Orchestrator Results ───────────────────────────────────────────────


def _make_orch_result(
    results: list[SearchResult] | None = None,
    total_raw: int | None = None,
) -> OrchestratorResult:
    """Build an OrchestratorResult for testing."""
    results = results or []
    return OrchestratorResult(
        results=results,
        provider_statuses=[
            ProviderStatus(
                provider_name="duckduckgo",
                status=ProviderStatusCode.SUCCESS,
                result_count=len(results),
            ),
        ],
        total_raw_results=total_raw if total_raw is not None else len(results),
    )


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_collector_success_domain():
    """Search collector returns results for a domain target."""
    collector = SearchCollector()

    orch_result = _make_orch_result([
        SearchResult(
            title="Example Domain - Test Page",
            url="https://example.com/page",
            snippet="This is an example domain.",
            provider="duckduckgo",
        ),
    ])

    with patch.object(collector._orchestrator, "search", return_value=orch_result):
        result = await collector.collect("example.com", TargetType.DOMAIN)

    assert result.status == ObservationStatus.SUCCESS
    assert result.collector_name == "search"
    assert result.raw_response["query"] == "site:example.com"
    assert "results" in result.raw_response
    assert "result_count" in result.raw_response
    assert result.raw_response["result_count"] == 1


@pytest.mark.asyncio
async def test_search_collector_no_results():
    """Search collector handles empty results gracefully."""
    collector = SearchCollector()

    orch_result = _make_orch_result([])

    with patch.object(collector._orchestrator, "search", return_value=orch_result):
        result = await collector.collect("nonexistent.xyz", TargetType.DOMAIN)

    assert result.status == ObservationStatus.SUCCESS
    assert result.raw_response["result_count"] == 0


@pytest.mark.asyncio
async def test_search_collector_username_query():
    """Search collector builds correct query for username targets."""
    collector = SearchCollector()

    orch_result = _make_orch_result([])

    with patch.object(collector._orchestrator, "search", return_value=orch_result):
        result = await collector.collect("johndoe", TargetType.USERNAME)

    assert "johndoe" in result.raw_response["query"]


@pytest.mark.asyncio
async def test_search_collector_health_check():
    """Search collector health check returns correct info."""
    collector = SearchCollector()
    health = await collector.health_check()
    assert health["name"] == "search"
    assert health["api_key_configured"] is True
    assert health["rate_limit_rpm"] == 10


def test_search_collector_supported_types():
    """Search collector supports expected target types."""
    collector = SearchCollector()
    assert TargetType.DOMAIN in collector.supported_target_types
    assert TargetType.IP in collector.supported_target_types
    assert TargetType.URL in collector.supported_target_types
    assert TargetType.USERNAME in collector.supported_target_types
    assert TargetType.EMAIL in collector.supported_target_types
    assert TargetType.ORGANIZATION in collector.supported_target_types


def test_build_query_domain():
    """Query builder produces correct format for domains."""
    collector = SearchCollector()
    assert collector._build_query("example.com", TargetType.DOMAIN) == "site:example.com"


def test_build_query_username():
    """Query builder produces correct format for usernames."""
    collector = SearchCollector()
    assert collector._build_query("johndoe", TargetType.USERNAME) == '"johndoe"'


def test_build_query_ip():
    """Query builder produces correct format for IPs."""
    collector = SearchCollector()
    assert collector._build_query("1.2.3.4", TargetType.IP) == '"1.2.3.4"'


@pytest.mark.asyncio
async def test_search_collector_provider_metadata_in_result():
    """Search results include provider metadata."""
    collector = SearchCollector()

    orch_result = _make_orch_result([
        SearchResult(
            title="Test",
            url="https://test.com",
            snippet="Test",
            provider="duckduckgo",
        ),
    ])

    with patch.object(collector._orchestrator, "search", return_value=orch_result):
        result = await collector.collect("test.com", TargetType.DOMAIN)

    assert "providers" in result.metadata
    assert "duckduckgo" in result.metadata["providers"]
    assert "provider_statuses" in result.metadata


@pytest.mark.asyncio
async def test_search_collector_version():
    """Search collector version is 1.2.0 (multi-provider)."""
    collector = SearchCollector()
    assert collector.version == "1.2.0"
