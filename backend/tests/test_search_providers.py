"""Tests for the multi-provider search layer.

Covers:
- SearchProvider interface compliance
- SearXNG response parsing
- Provider failure / fallback
- Concurrent multi-provider search
- URL deduplication
- Configuration-driven provider creation
- Non-username investigations using the search layer
- SearchRequest / SearchResult model validation
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.collectors.search_providers.base import (
    ProviderStatus,
    ProviderStatusCode,
    SearchProvider,
    SearchProviderResponse,
    SearchRequest,
    SearchResult,
)
from app.collectors.search_providers.duckduckgo import (
    DuckDuckGoProvider,
    _parse_ddg_api_json,
    _parse_ddg_html,
    _parse_ddg_lite_html,
)
from app.collectors.search_providers.orchestrator import (
    MultiProviderOrchestrator,
    OrchestratorResult,
    _deduplicate_results,
    _interleave_rank,
)
from app.collectors.search_providers.searxng import (
    SearXNGProvider,
    _parse_searxng_results,
)
from app.collectors.search_collector import (
    SearchCollector,
    _build_query,
    _build_providers,
    _extract_entities,
)
from app.models import ObservationStatus, TargetType


# ── SearchRequest / SearchResult models ─────────────────────────────────────


class TestSearchModels:
    """Validate normalized search types."""

    def test_search_request_defaults(self):
        req = SearchRequest(query="test")
        assert req.query == "test"
        assert req.max_results == 10
        assert req.timeout == 10.0

    def test_search_request_custom(self):
        req = SearchRequest(query="example", max_results=5, timeout=3.0)
        assert req.max_results == 5
        assert req.timeout == 3.0

    def test_search_result_normalized_url(self):
        r = SearchResult(title="T", url="HTTPS://Example.COM/Page/")
        assert r.normalized_url() == "https://example.com/page"

    def test_search_result_normalized_url_empty(self):
        r = SearchResult(title="T", url="")
        assert r.normalized_url() == ""

    def test_provider_status_defaults(self):
        ps = ProviderStatus(provider_name="test")
        assert ps.status == ProviderStatusCode.SUCCESS
        assert ps.result_count == 0
        assert ps.error_message == ""

    def test_search_provider_response_auto_status(self):
        resp = SearchProviderResponse(provider_name="test_prov")
        assert resp.status.provider_name == "test_prov"


# ── SearchProvider interface ─────────────────────────────────────────────────


class TestProviderInterface:
    """Verify providers implement SearchProvider correctly."""

    def test_duckduckgo_is_search_provider(self):
        assert issubclass(DuckDuckGoProvider, SearchProvider)

    def test_searxng_is_search_provider(self):
        assert issubclass(SearXNGProvider, SearchProvider)

    def test_duckduckgo_name(self):
        assert DuckDuckGoProvider().name == "duckduckgo"

    def test_searxng_name(self):
        assert SearXNGProvider(base_url="http://localhost:8080").name == "searxng"


# ── DuckDuckGo parsing ──────────────────────────────────────────────────────


class TestDuckDuckGoParsing:
    """Test DDG HTML/Lite/API parsing functions."""

    def test_parse_ddg_html_with_results(self):
        html = """<html><body>
        <div class="result__body">
            <h2 class="result__title">
                <a href="https://ddg.com/?uddg=https%3A%2F%2Fexample.com">
                    Example Title</a>
            </h2>
            <a class="result__url" href="https://example.com">example.com</a>
            <div class="result__snippet">Example snippet text.</div>
        </div>
        </body></html>"""
        results = _parse_ddg_html(html)
        assert len(results) >= 1
        assert results[0]["title"] == "Example Title"
        assert "example.com" in results[0]["url"]

    def test_parse_ddg_html_empty(self):
        results = _parse_ddg_html("<html><body><p>No results</p></body></html>")
        assert results == []

    def test_parse_ddg_lite_html(self):
        html = """<html><body><table>
        <tr>
            <td><a class="result-link" href="https://example.com">Example</a></td>
            <td class="result-snippet">A snippet.</td>
        </tr>
        </table></body></html>"""
        results = _parse_ddg_lite_html(html)
        assert len(results) >= 1
        assert results[0]["title"] == "Example"

    def test_parse_ddg_api_json(self):
        data = {
            "Abstract": "Example abstract",
            "Heading": "Example",
            "AbstractURL": "https://example.com",
            "RelatedTopics": [
                {"Text": "Related topic 1", "FirstURL": "https://related.com"},
            ],
            "Results": [],
        }
        results = _parse_ddg_api_json(data)
        assert len(results) >= 1
        assert results[0]["title"] == "Example"
        assert results[0]["url"] == "https://example.com"

    def test_parse_ddg_api_json_empty(self):
        results = _parse_ddg_api_json({})
        assert results == []


# ── SearXNG parsing ──────────────────────────────────────────────────────────


class TestSearXNGParsing:
    """Test SearXNG JSON response parsing."""

    def test_parse_basic_results(self):
        data = {
            "results": [
                {
                    "title": "SearXNG Result 1",
                    "url": "https://result1.com",
                    "content": "First result snippet.",
                    "engine": "google",
                },
                {
                    "title": "SearXNG Result 2",
                    "url": "https://result2.com",
                    "content": "Second result snippet.",
                    "engine": "bing",
                },
            ],
            "number_of_results": 2,
        }
        results = _parse_searxng_results(data, max_results=10)
        assert len(results) == 2
        assert results[0]["title"] == "SearXNG Result 1"
        assert results[0]["url"] == "https://result1.com"
        assert results[0]["snippet"] == "First result snippet."

    def test_parse_empty_results(self):
        results = _parse_searxng_results({"results": []}, max_results=10)
        assert results == []

    def test_parse_missing_url_skipped(self):
        data = {
            "results": [
                {"title": "No URL", "content": "Snippet"},
                {"title": "Has URL", "url": "https://example.com", "content": "OK"},
            ]
        }
        results = _parse_searxng_results(data, max_results=10)
        assert len(results) == 1
        assert results[0]["url"] == "https://example.com"

    def test_parse_respects_max_results(self):
        data = {
            "results": [
                {"title": f"R{i}", "url": f"https://example{i}.com", "content": ""}
                for i in range(20)
            ]
        }
        results = _parse_searxng_results(data, max_results=5)
        assert len(results) == 5

    def test_parse_non_dict_items_skipped(self):
        data = {"results": ["not a dict", {"title": "OK", "url": "https://ok.com", "content": ""}]}
        results = _parse_searxng_results(data, max_results=10)
        assert len(results) == 1


# ── SearXNG provider failure ────────────────────────────────────────────────


class TestSearXNGProviderFailure:
    """SearXNG must fail gracefully when the instance is unreachable."""

    @pytest.mark.asyncio
    async def test_searxng_unavailable_returns_error_status(self):
        provider = SearXNGProvider(base_url="http://unreachable-host:9999")
        request = SearchRequest(query="test", timeout=2.0)
        response = await provider.search(request)

        assert response.provider_name == "searxng"
        assert response.results == []
        assert response.status.status in (
            ProviderStatusCode.ERROR,
            ProviderStatusCode.TIMEOUT,
        )
        assert response.status.error_message  # non-empty

    @pytest.mark.asyncio
    async def test_searxng_health_check_unavailable(self):
        provider = SearXNGProvider(base_url="http://unreachable-host:9999")
        health = await provider.health_check()
        assert health["available"] is False


# ── URL deduplication ────────────────────────────────────────────────────────


class TestURLDeduplication:
    """Test URL normalization and dedup logic."""

    def test_dedup_exact_duplicates(self):
        results = [
            SearchResult(title="A", url="https://example.com", provider="ddg"),
            SearchResult(title="B", url="https://example.com", provider="searxng"),
        ]
        deduped = _deduplicate_results(results)
        assert len(deduped) == 1
        assert deduped[0].title == "A"  # first wins

    def test_dedup_case_insensitive(self):
        results = [
            SearchResult(title="A", url="https://Example.COM/Page", provider="ddg"),
            SearchResult(title="B", url="https://example.com/page", provider="searxng"),
        ]
        deduped = _deduplicate_results(results)
        assert len(deduped) == 1

    def test_dedup_trailing_slash(self):
        results = [
            SearchResult(title="A", url="https://example.com/", provider="ddg"),
            SearchResult(title="B", url="https://example.com", provider="searxng"),
        ]
        deduped = _deduplicate_results(results)
        assert len(deduped) == 1

    def test_dedup_different_urls_kept(self):
        results = [
            SearchResult(title="A", url="https://example.com/a", provider="ddg"),
            SearchResult(title="B", url="https://example.com/b", provider="searxng"),
        ]
        deduped = _deduplicate_results(results)
        assert len(deduped) == 2

    def test_dedup_empty_url_skipped(self):
        results = [
            SearchResult(title="A", url="", provider="ddg"),
            SearchResult(title="B", url="https://example.com", provider="searxng"),
        ]
        deduped = _deduplicate_results(results)
        assert len(deduped) == 1
        assert deduped[0].url == "https://example.com"


# ── Interleaved ranking ──────────────────────────────────────────────────────


class TestInterleavedRanking:
    """Test balanced interleaving across providers."""

    def test_interleave_two_providers(self):
        results = [
            SearchResult(title="DDG-1", url="https://a.com", provider="ddg", rank=0),
            SearchResult(title="DDG-2", url="https://b.com", provider="ddg", rank=1),
            SearchResult(title="SX-1", url="https://c.com", provider="searxng", rank=0),
            SearchResult(title="SX-2", url="https://d.com", provider="searxng", rank=1),
        ]
        ranked = _interleave_rank(results, ["ddg", "searxng"])
        providers = [r.provider for r in ranked]
        assert providers == ["ddg", "searxng", "ddg", "searxng"]

    def test_interleave_uneven_counts(self):
        results = [
            SearchResult(title="DDG-1", url="https://a.com", provider="ddg", rank=0),
            SearchResult(title="DDG-2", url="https://b.com", provider="ddg", rank=1),
            SearchResult(title="DDG-3", url="https://c.com", provider="ddg", rank=2),
            SearchResult(title="SX-1", url="https://d.com", provider="searxng", rank=0),
        ]
        ranked = _interleave_rank(results, ["ddg", "searxng"])
        assert len(ranked) == 4
        # First two should be ddg-0, searxng-0
        assert ranked[0].provider == "ddg"
        assert ranked[1].provider == "searxng"

    def test_interleave_empty(self):
        assert _interleave_rank([], ["ddg"]) == []


# ── Multi-provider orchestrator ──────────────────────────────────────────────


class _MockProvider(SearchProvider):
    """Test double for SearchProvider."""

    def __init__(self, provider_name: str, results: list[SearchResult] | None = None,
                 fail: bool = False):
        self._name = provider_name
        self._results = results or []
        self._fail = fail

    @property
    def name(self) -> str:
        return self._name

    async def search(self, request: SearchRequest) -> SearchProviderResponse:
        if self._fail:
            raise ConnectionError(f"{self._name} failed")
        return SearchProviderResponse(
            provider_name=self._name,
            results=self._results[:request.max_results],
            status=ProviderStatus(
                provider_name=self._name,
                status=ProviderStatusCode.SUCCESS,
                result_count=len(self._results[:request.max_results]),
            ),
        )


class TestMultiProviderOrchestrator:
    """Test concurrent multi-provider execution."""

    @pytest.mark.asyncio
    async def test_single_provider_success(self):
        provider = _MockProvider(
            "test",
            results=[SearchResult(title="R1", url="https://a.com", provider="test")],
        )
        orch = MultiProviderOrchestrator([provider])
        result = await orch.search(SearchRequest(query="test"))

        assert len(result.results) == 1
        assert result.provider_statuses[0].status == ProviderStatusCode.SUCCESS

    @pytest.mark.asyncio
    async def test_two_providers_concurrent(self):
        p1 = _MockProvider(
            "p1",
            results=[SearchResult(title="P1-R1", url="https://a.com", provider="p1")],
        )
        p2 = _MockProvider(
            "p2",
            results=[SearchResult(title="P2-R1", url="https://b.com", provider="p2")],
        )
        orch = MultiProviderOrchestrator([p1, p2])
        result = await orch.search(SearchRequest(query="test"))

        assert len(result.results) == 2
        assert len(result.provider_statuses) == 2
        assert all(ps.status == ProviderStatusCode.SUCCESS for ps in result.provider_statuses)

    @pytest.mark.asyncio
    async def test_one_provider_fails_other_succeeds(self):
        p_ok = _MockProvider(
            "ok",
            results=[SearchResult(title="Good", url="https://ok.com", provider="ok")],
        )
        p_fail = _MockProvider("bad", fail=True)
        orch = MultiProviderOrchestrator([p_ok, p_fail])
        result = await orch.search(SearchRequest(query="test"))

        # Good results still returned
        assert len(result.results) == 1
        assert result.results[0].title == "Good"

        # Failed provider is recorded
        statuses_by_name = {ps.provider_name: ps for ps in result.provider_statuses}
        assert statuses_by_name["ok"].status == ProviderStatusCode.SUCCESS
        assert statuses_by_name["bad"].status == ProviderStatusCode.ERROR

    @pytest.mark.asyncio
    async def test_both_providers_fail(self):
        p1 = _MockProvider("p1", fail=True)
        p2 = _MockProvider("p2", fail=True)
        orch = MultiProviderOrchestrator([p1, p2])
        result = await orch.search(SearchRequest(query="test"))

        assert result.results == []
        assert all(ps.status == ProviderStatusCode.ERROR for ps in result.provider_statuses)

    @pytest.mark.asyncio
    async def test_dedup_across_providers(self):
        p1 = _MockProvider(
            "p1",
            results=[SearchResult(title="A", url="https://example.com", provider="p1")],
        )
        p2 = _MockProvider(
            "p2",
            results=[SearchResult(title="B", url="https://example.com", provider="p2")],
        )
        orch = MultiProviderOrchestrator([p1, p2])
        result = await orch.search(SearchRequest(query="test"))

        assert len(result.results) == 1  # deduped
        assert result.deduplicated_count == 1

    @pytest.mark.asyncio
    async def test_empty_provider_list(self):
        orch = MultiProviderOrchestrator([])
        result = await orch.search(SearchRequest(query="test"))
        assert result.results == []


# ── Configuration-driven provider creation ───────────────────────────────────


class TestProviderConfiguration:
    """Test _build_providers configuration logic."""

    def test_default_config_creates_only_duckduckgo(self):
        config = {
            "searxng_base_url": "",
            "searxng_enabled": True,
            "provider_timeout": 10.0,
            "max_results_per_provider": 10,
        }
        providers = _build_providers(config)
        assert len(providers) == 1
        assert providers[0].name == "duckduckgo"

    def test_searxng_url_creates_both_providers(self):
        config = {
            "searxng_base_url": "http://searxng:8080",
            "searxng_enabled": True,
            "provider_timeout": 10.0,
            "max_results_per_provider": 10,
        }
        providers = _build_providers(config)
        assert len(providers) == 2
        names = {p.name for p in providers}
        assert names == {"duckduckgo", "searxng"}

    def test_searxng_disabled_skipped(self):
        config = {
            "searxng_base_url": "http://searxng:8080",
            "searxng_enabled": False,
            "provider_timeout": 10.0,
            "max_results_per_provider": 10,
        }
        providers = _build_providers(config)
        assert len(providers) == 1
        assert providers[0].name == "duckduckgo"


# ── Non-username investigation types ─────────────────────────────────────────


class TestNonUsernameInvestigations:
    """Search layer works for all investigation types, not just username."""

    def test_domain_query(self):
        assert _build_query("example.com", TargetType.DOMAIN) == "site:example.com"

    def test_email_query(self):
        assert _build_query("user@example.com", TargetType.EMAIL) == '"user@example.com"'

    def test_ip_query(self):
        assert _build_query("8.8.8.8", TargetType.IP) == '"8.8.8.8"'

    def test_org_query(self):
        q = _build_query("Acme Corp", TargetType.ORGANIZATION)
        assert "Acme Corp" in q
        assert "company" in q.lower() or "organization" in q.lower()

    def test_url_query(self):
        assert _build_query("https://example.com/path", TargetType.URL) == '"https://example.com/path"'

    @pytest.mark.asyncio
    async def test_search_collector_domain_uses_orchestrator(self):
        """SearchCollector for domain target uses multi-provider orchestrator."""
        collector = SearchCollector()

        # Mock the orchestrator
        mock_orch_result = OrchestratorResult(
            results=[
                SearchResult(
                    title="Example Domain",
                    url="https://example.com",
                    snippet="Test snippet",
                    provider="duckduckgo",
                ),
            ],
            provider_statuses=[
                ProviderStatus(
                    provider_name="duckduckgo",
                    status=ProviderStatusCode.SUCCESS,
                    result_count=1,
                ),
            ],
            total_raw_results=1,
        )

        with patch.object(collector._orchestrator, "search", return_value=mock_orch_result):
            result = await collector._collect("example.com", TargetType.DOMAIN)

        assert result.status == ObservationStatus.SUCCESS
        assert result.collector_name == "search"
        assert result.raw_response["result_count"] == 1
        assert result.raw_response["results"][0]["provider"] == "duckduckgo"
        assert "providers" in result.metadata

    @pytest.mark.asyncio
    async def test_search_collector_email_uses_orchestrator(self):
        """SearchCollector for email target uses multi-provider orchestrator."""
        collector = SearchCollector()

        mock_orch_result = OrchestratorResult(
            results=[
                SearchResult(
                    title="Email ref",
                    url="https://ref.com/user",
                    snippet="user@example.com mentioned",
                    provider="duckduckgo",
                ),
            ],
            provider_statuses=[
                ProviderStatus(
                    provider_name="duckduckgo",
                    status=ProviderStatusCode.SUCCESS,
                    result_count=1,
                ),
            ],
            total_raw_results=1,
        )

        with patch.object(collector._orchestrator, "search", return_value=mock_orch_result):
            result = await collector._collect("user@example.com", TargetType.EMAIL)

        assert result.status == ObservationStatus.SUCCESS
        assert result.raw_response["query"] == '"user@example.com"'

    @pytest.mark.asyncio
    async def test_search_collector_org_uses_orchestrator(self):
        """SearchCollector for organization target uses multi-provider orchestrator."""
        collector = SearchCollector()

        mock_orch_result = OrchestratorResult(
            results=[],
            provider_statuses=[
                ProviderStatus(
                    provider_name="duckduckgo",
                    status=ProviderStatusCode.SUCCESS,
                    result_count=0,
                ),
            ],
            total_raw_results=0,
        )

        with patch.object(collector._orchestrator, "search", return_value=mock_orch_result):
            result = await collector._collect("Acme Corp", TargetType.ORGANIZATION)

        assert result.status == ObservationStatus.SUCCESS
        assert result.confidence == 0.3  # empty results → low confidence


# ── Entity extraction ────────────────────────────────────────────────────────


class TestEntityExtraction:
    """Test entity extraction from search results."""

    def test_extracts_domains_emails_ips(self):
        results = [
            {
                "title": "Test Page",
                "url": "https://example.com/page",
                "snippet": "Contact admin@example.com. Server at 192.168.1.100.",
            }
        ]
        entities = _extract_entities(results)
        assert "example.com" in entities["domains"]
        assert "admin@example.com" in entities["emails"]
        assert "192.168.1.100" in entities["ips"]
        assert any("example.com" in u for u in entities["urls"])

    def test_excludes_file_extensions(self):
        results = [
            {"title": "T", "url": "https://x.com", "snippet": "load style.css image.png"}
        ]
        entities = _extract_entities(results)
        assert "style.css" not in entities["domains"]
        assert "image.png" not in entities["domains"]

    def test_empty_results(self):
        entities = _extract_entities([])
        assert entities == {"domains": [], "emails": [], "urls": [], "ips": []}


# ── SearchCollector integration ──────────────────────────────────────────────


class TestSearchCollectorIntegration:
    """Verify SearchCollector works as an OSINTCollector."""

    def test_supported_target_types(self):
        collector = SearchCollector()
        assert TargetType.DOMAIN in collector.supported_target_types
        assert TargetType.IP in collector.supported_target_types
        assert TargetType.URL in collector.supported_target_types
        assert TargetType.USERNAME in collector.supported_target_types
        assert TargetType.EMAIL in collector.supported_target_types
        assert TargetType.ORGANIZATION in collector.supported_target_types

    def test_version_updated(self):
        collector = SearchCollector()
        assert collector.version == "1.2.0"

    def test_no_api_key_required(self):
        collector = SearchCollector()
        assert not collector.requires_api_key

    @pytest.mark.asyncio
    async def test_health_check(self):
        collector = SearchCollector()
        health = await collector.health_check()
        assert health["name"] == "search"
        assert health["api_key_configured"] is True

    def test_has_orchestrator_with_providers(self):
        collector = SearchCollector()
        assert hasattr(collector, "_orchestrator")
        assert "duckduckgo" in collector._orchestrator.provider_names
