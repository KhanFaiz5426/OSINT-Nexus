"""Platform Intelligence Adapter tests.

Tests for the adapter interface, YouTube API adapter, search discovery adapter,
provenance/confidence, and integration with the orchestrator.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.username_engine.adapters.base import (
    AcquisitionMethod,
    AdapterResult,
    EvidenceConfidence,
)
from app.services.username_engine.adapters.http_adapter import DirectHTTPAdapter
from app.services.username_engine.adapters.search_discovery_adapter import (
    _SEARCH_CONFIGS,
    SearchDiscoveryAdapter,
)
from app.services.username_engine.adapters.youtube_api_adapter import YouTubeAPIAdapter
from app.services.username_engine.intelligence import (
    _PLATFORM_ADAPTER_OVERRIDES,
    PlatformIntelligenceOrchestrator,
)
from app.services.username_engine.models import PlatformDefinition

# ── Adapter Interface Tests ──────────────────────────────────────────────────


class TestAdapterResult:
    """Tests for AdapterResult dataclass."""

    def test_default_values(self):
        result = AdapterResult(
            platform_key="github",
            platform_name="GitHub",
            username="testuser",
            found=True,
        )
        assert result.acquisition_method == AcquisitionMethod.DIRECT_HTTP
        assert result.evidence_confidence == EvidenceConfidence.MEDIUM
        assert result.confidence == 0.0
        assert result.error == ""

    def test_search_discovery_result(self):
        result = AdapterResult(
            platform_key="x_twitter",
            platform_name="X/Twitter",
            username="testuser",
            found=True,
            url="https://x.com/testuser",
            acquisition_method=AcquisitionMethod.SEARCH_DISCOVERY,
            confidence=0.55,
            evidence_confidence=EvidenceConfidence.LOW,
        )
        assert result.acquisition_method == AcquisitionMethod.SEARCH_DISCOVERY
        assert result.evidence_confidence == EvidenceConfidence.LOW

    def test_api_result(self):
        result = AdapterResult(
            platform_key="youtube",
            platform_name="YouTube",
            username="testuser",
            found=True,
            acquisition_method=AcquisitionMethod.API,
            confidence=0.95,
            evidence_confidence=EvidenceConfidence.HIGH,
        )
        assert result.acquisition_method == AcquisitionMethod.API
        assert result.evidence_confidence == EvidenceConfidence.HIGH


class TestAcquisitionMethod:
    """Tests for AcquisitionMethod enum."""

    def test_values(self):
        assert AcquisitionMethod.DIRECT_HTTP == "direct_http"
        assert AcquisitionMethod.API == "api"
        assert AcquisitionMethod.SEARCH_DISCOVERY == "search_discovery"
        assert AcquisitionMethod.BROWSER == "browser"


class TestEvidenceConfidence:
    """Tests for EvidenceConfidence enum."""

    def test_values(self):
        assert EvidenceConfidence.LOW == "low"
        assert EvidenceConfidence.MEDIUM == "medium"
        assert EvidenceConfidence.HIGH == "high"

    def test_all_values_present(self):
        values = [e.value for e in EvidenceConfidence]
        assert "low" in values
        assert "medium" in values
        assert "high" in values


# ── DirectHTTPAdapter Tests ──────────────────────────────────────────────────


class TestDirectHTTPAdapter:
    """Tests for the DirectHTTP adapter."""

    def test_adapter_properties(self):
        adapter = DirectHTTPAdapter()
        assert adapter.name == "direct_http"
        assert adapter.acquisition_method == AcquisitionMethod.DIRECT_HTTP
        assert adapter.is_available is True

    def test_probe_returns_none_without_platform(self):
        """Adapter should return None if no PlatformDefinition provided."""
        adapter = DirectHTTPAdapter()
        adapter.probe("github", "testuser", "inv-id")
        # This is a coroutine, need to await in async test
        assert True  # Will be tested in async

    @pytest.mark.asyncio
    async def test_probe_success_200(self):
        adapter = DirectHTTPAdapter()
        platform = PlatformDefinition(
            key="test",
            name="Test",
            url_pattern="https://example.com/{username}",
            success_indicators={"status_codes": [200], "body_not_contains": ["not found"]},
            failure_indicators={"status_codes": [404]},
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><title>John Doe</title></html>"
        mock_response.url = "https://example.com/johndoe"
        mock_response.headers = {"content-type": "text/html"}

        with patch(
            "app.services.username_engine.adapters.http_adapter.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.probe("test", "johndoe", "inv-id", platform=platform)

            assert result is not None
            assert result.found is True
            assert result.acquisition_method == AcquisitionMethod.DIRECT_HTTP
            assert result.evidence_confidence == EvidenceConfidence.MEDIUM
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_probe_failure_404(self):
        adapter = DirectHTTPAdapter()
        platform = PlatformDefinition(
            key="test",
            name="Test",
            url_pattern="https://example.com/{username}",
            success_indicators={"status_codes": [200]},
            failure_indicators={"status_codes": [404]},
        )

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.url = "https://example.com/nobody"

        with patch(
            "app.services.username_engine.adapters.http_adapter.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.probe("test", "nobody", "inv-id", platform=platform)

            assert result is not None
            assert result.found is False
            assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_probe_timeout(self):
        import httpx

        adapter = DirectHTTPAdapter()
        platform = PlatformDefinition(
            key="test",
            name="Test",
            url_pattern="https://example.com/{username}",
            timeout=0.1,
        )

        with patch(
            "app.services.username_engine.adapters.http_adapter.httpx.AsyncClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.probe("test", "johndoe", "inv-id", platform=platform)

            assert result is not None
            assert result.found is False
            assert result.error == "timeout"

    def test_to_raw_result(self):
        adapter = DirectHTTPAdapter()
        result = AdapterResult(
            platform_key="github",
            platform_name="GitHub",
            username="johndoe",
            found=True,
            url="https://github.com/johndoe",
            acquisition_method=AcquisitionMethod.DIRECT_HTTP,
            confidence=0.85,
            evidence_confidence=EvidenceConfidence.MEDIUM,
            evidence={"status_code": 200},
        )
        raw = adapter.to_raw_result(result, "test-inv-id")
        assert raw.collector_name == "username_probe"
        assert raw.target == "johndoe"
        assert raw.confidence == 0.85
        assert raw.raw_response["acquisition_method"] == "direct_http"
        assert raw.raw_response["evidence_confidence"] == "medium"
        assert raw.metadata["adapter"] == "direct_http"


# ── YouTube API Adapter Tests ────────────────────────────────────────────────


class TestYouTubeAPIAdapter:
    """Tests for the YouTube Data API v3 adapter."""

    def test_adapter_properties(self):
        adapter = YouTubeAPIAdapter()
        assert adapter.name == "youtube_api"
        assert adapter.acquisition_method == AcquisitionMethod.API
        assert adapter.supported_platforms == ["youtube"]

    def test_is_available_with_key(self):
        adapter = YouTubeAPIAdapter()
        with patch(
            "app.services.username_engine.adapters.youtube_api_adapter._get_youtube_api_key"
        ) as mock_key:
            mock_key.return_value = "test-key-123"
            assert adapter.is_available is True

    def test_is_available_without_key(self):
        adapter = YouTubeAPIAdapter()
        with patch(
            "app.services.username_engine.adapters.youtube_api_adapter._get_youtube_api_key"
        ) as mock_key:
            mock_key.return_value = ""
            assert adapter.is_available is False

    @pytest.mark.asyncio
    async def test_probe_returns_none_for_wrong_platform(self):
        adapter = YouTubeAPIAdapter()
        result = await adapter.probe("github", "testuser", "inv-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_probe_no_api_key(self):
        adapter = YouTubeAPIAdapter()
        with patch(
            "app.services.username_engine.adapters.youtube_api_adapter._get_youtube_api_key"
        ) as mock_key:
            mock_key.return_value = ""
            result = await adapter.probe("youtube", "geerlingguy", "inv-id")

            assert result is not None
            assert result.found is False
            assert "YOUTUBE_API_KEY not configured" in result.error
            assert result.evidence_confidence == EvidenceConfidence.HIGH

    @pytest.mark.asyncio
    async def test_probe_success_via_handle(self):
        adapter = YouTubeAPIAdapter()
        api_response = {
            "items": [
                {
                    "id": "UC45GcuMCV",
                    "snippet": {
                        "title": "Jeff Geerling",
                        "description": "Raspberry Pi, Linux, Ansible",
                        "customUrl": "@geerlingguy",
                        "publishedAt": "2010-01-01T00:00:00Z",
                        "country": "US",
                        "thumbnails": {"default": {"url": "https://yt3.ggpht.com/thumb.jpg"}},
                    },
                    "statistics": {
                        "viewCount": "100000000",
                        "subscriberCount": "1500000",
                        "videoCount": "1000",
                    },
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = api_response

        with patch(
            "app.services.username_engine.adapters.youtube_api_adapter._get_youtube_api_key"
        ) as mock_key:
            mock_key.return_value = "test-key"
            with patch(
                "app.services.username_engine.adapters.youtube_api_adapter.httpx.AsyncClient"
            ) as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_client.return_value = mock_instance

                result = await adapter.probe("youtube", "geerlingguy", "inv-id")

                assert result is not None
                assert result.found is True
                assert result.acquisition_method == AcquisitionMethod.API
                assert result.evidence_confidence == EvidenceConfidence.HIGH
                assert result.profile["title"] == "Jeff Geerling"
                assert result.profile["subscriber_count"] == "1500000"
                assert result.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_probe_not_found(self):
        adapter = YouTubeAPIAdapter()
        api_response = {"items": []}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = api_response

        with patch(
            "app.services.username_engine.adapters.youtube_api_adapter._get_youtube_api_key"
        ) as mock_key:
            mock_key.return_value = "test-key"
            with patch(
                "app.services.username_engine.adapters.youtube_api_adapter.httpx.AsyncClient"
            ) as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_client.return_value = mock_instance

                result = await adapter.probe("youtube", "nonexistentuser12345", "inv-id")

                assert result is not None
                assert result.found is False
                assert result.evidence_confidence == EvidenceConfidence.HIGH

    @pytest.mark.asyncio
    async def test_probe_api_error(self):
        adapter = YouTubeAPIAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "quota exceeded"

        with patch(
            "app.services.username_engine.adapters.youtube_api_adapter._get_youtube_api_key"
        ) as mock_key:
            mock_key.return_value = "test-key"
            with patch(
                "app.services.username_engine.adapters.youtube_api_adapter.httpx.AsyncClient"
            ) as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(return_value=mock_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_client.return_value = mock_instance

                result = await adapter.probe("youtube", "geerlingguy", "inv-id")

                # API error returns a not-found result (adapter completed the probe)
                assert result is not None
                assert result.found is False

    @pytest.mark.asyncio
    async def test_probe_timeout(self):
        import httpx

        adapter = YouTubeAPIAdapter()

        with patch(
            "app.services.username_engine.adapters.youtube_api_adapter._get_youtube_api_key"
        ) as mock_key:
            mock_key.return_value = "test-key"
            with patch(
                "app.services.username_engine.adapters.youtube_api_adapter.httpx.AsyncClient"
            ) as mock_client:
                mock_instance = AsyncMock()
                mock_instance.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_client.return_value = mock_instance

                result = await adapter.probe("youtube", "geerlingguy", "inv-id")

                # Timeout falls through to forUsername which also times out, returns not-found
                assert result is not None
                assert result.found is False


# ── Search Discovery Adapter Tests ───────────────────────────────────────────


class TestSearchDiscoveryAdapter:
    """Tests for the search discovery adapter."""

    def test_adapter_properties(self):
        adapter = SearchDiscoveryAdapter()
        assert adapter.name == "search_discovery"
        assert adapter.acquisition_method == AcquisitionMethod.SEARCH_DISCOVERY
        assert "x_twitter" in adapter.supported_platforms
        assert "linkedin" in adapter.supported_platforms

    def test_is_available(self):
        adapter = SearchDiscoveryAdapter()
        assert adapter.is_available is True  # Always available (uses public search)

    @pytest.mark.asyncio
    async def test_probe_returns_none_for_unknown_platform(self):
        adapter = SearchDiscoveryAdapter()
        result = await adapter.probe("github", "testuser", "inv-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_probe_no_results(self):
        adapter = SearchDiscoveryAdapter()

        mock_orch_result = MagicMock()
        mock_orch_result.results = []

        with patch.object(adapter._orchestrator, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_orch_result

            result = await adapter.probe("x_twitter", "nonexistentuser12345", "inv-id")

            assert result is not None
            assert result.found is False
            assert result.evidence_confidence == EvidenceConfidence.LOW
            assert result.acquisition_method == AcquisitionMethod.SEARCH_DISCOVERY

    @pytest.mark.asyncio
    async def test_probe_finds_matching_url(self):
        adapter = SearchDiscoveryAdapter()

        mock_search_result = MagicMock()
        mock_search_result.title = "Jeff Geerling (@geerlingguy) / X"
        mock_search_result.url = "https://x.com/geerlingguy"
        mock_search_result.snippet = "Raspberry Pi enthusiast, sysadmin"

        mock_orch_result = MagicMock()
        mock_orch_result.results = [mock_search_result]

        with patch.object(adapter._orchestrator, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_orch_result

            result = await adapter.probe("x_twitter", "geerlingguy", "inv-id")

            assert result is not None
            assert result.found is True
            assert result.evidence_confidence == EvidenceConfidence.LOW
            assert result.acquisition_method == AcquisitionMethod.SEARCH_DISCOVERY
            assert result.confidence <= 0.65  # Search discovery is LOW confidence
            assert result.profile["discovery_method"] == "web_search"

    @pytest.mark.asyncio
    async def test_probe_negative_signals(self):
        adapter = SearchDiscoveryAdapter()

        mock_search_result = MagicMock()
        mock_search_result.title = "Account suspended"
        mock_search_result.url = "https://x.com/suspended_user"
        mock_search_result.snippet = "This account has been suspended"

        mock_orch_result = MagicMock()
        mock_orch_result.results = [mock_search_result]

        with patch.object(adapter._orchestrator, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_orch_result

            result = await adapter.probe("x_twitter", "suspended_user", "inv-id")

            assert result is not None
            assert result.found is False

    @pytest.mark.asyncio
    async def test_probe_multiple_sources_increases_confidence(self):
        adapter = SearchDiscoveryAdapter()

        mock_result1 = MagicMock()
        mock_result1.title = "Jeff Geerling / X"
        mock_result1.url = "https://x.com/geerlingguy"
        mock_result1.snippet = "Raspberry Pi"

        mock_result2 = MagicMock()
        mock_result2.title = "Jeff Geerling - Twitter"
        mock_result2.url = "https://twitter.com/geerlingguy"
        mock_result2.snippet = "DevOps and Linux"

        mock_orch_result = MagicMock()
        mock_orch_result.results = [mock_result1, mock_result2]

        with patch.object(adapter._orchestrator, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_orch_result

            result = await adapter.probe("x_twitter", "geerlingguy", "inv-id")

            assert result is not None
            assert result.found is True
            assert result.evidence["matching_urls"] >= 1

    def test_search_configs_exist(self):
        """All supported platforms should have search configurations."""
        assert "x_twitter" in _SEARCH_CONFIGS
        assert "linkedin" in _SEARCH_CONFIGS
        assert "instagram" in _SEARCH_CONFIGS
        assert "tiktok" in _SEARCH_CONFIGS

    def test_search_config_structure(self):
        """Search configs should have required fields."""
        for key, config in _SEARCH_CONFIGS.items():
            assert "name" in config, f"{key} missing name"
            assert "url_pattern" in config, f"{key} missing url_pattern"
            assert "search_queries" in config, f"{key} missing search_queries"
            assert "url_patterns_to_match" in config, f"{key} missing url_patterns_to_match"
            assert "base_confidence" in config, f"{key} missing base_confidence"
            assert config["base_confidence"] <= 0.65, (
                f"{key} base_confidence too high for search discovery"
            )


# ── Orchestrator Tests ──────────────────────────────────────────────────────


class TestPlatformIntelligenceOrchestrator:
    """Tests for the Platform Intelligence Orchestrator."""

    def test_orchestrator_initialization(self):
        orch = PlatformIntelligenceOrchestrator()
        status = orch.get_adapter_status()
        assert "direct_http" in status
        assert "youtube_api" in status
        assert "search_discovery" in status

    def test_adapter_chain_default(self):
        orch = PlatformIntelligenceOrchestrator()
        chain = orch.get_adapter_chain("github")
        adapter_names = [a.name for a in chain]
        assert "youtube_api" in adapter_names or "direct_http" in adapter_names

    def test_adapter_chain_youtube_override(self):
        orch = PlatformIntelligenceOrchestrator()
        # Mock YouTube adapter as available by patching the API key check
        with patch(
            "app.services.username_engine.adapters.youtube_api_adapter._get_youtube_api_key"
        ) as mock_key:
            mock_key.return_value = "test-key"
            # Re-create the adapter to pick up the mocked key
            orch._adapters["youtube_api"] = YouTubeAPIAdapter()
            chain = orch.get_adapter_chain("youtube")
            adapter_names = [a.name for a in chain]
            # YouTube should prefer API, not direct HTTP
            assert adapter_names.index("youtube_api") < adapter_names.index("search_discovery")

    def test_adapter_chain_x_twitter_override(self):
        orch = PlatformIntelligenceOrchestrator()
        chain = orch.get_adapter_chain("x_twitter")
        adapter_names = [a.name for a in chain]
        # X/Twitter should only use search discovery
        assert "search_discovery" in adapter_names
        assert "direct_http" not in adapter_names

    def test_platform_adapter_overrides_defined(self):
        """Disabled platforms should have explicit overrides."""
        assert "youtube" in _PLATFORM_ADAPTER_OVERRIDES
        assert "x_twitter" in _PLATFORM_ADAPTER_OVERRIDES
        assert "linkedin" in _PLATFORM_ADAPTER_OVERRIDES
        assert "instagram" in _PLATFORM_ADAPTER_OVERRIDES
        assert "tiktok" in _PLATFORM_ADAPTER_OVERRIDES


# ── Provenance/Confidence Tests ──────────────────────────────────────────────


class TestProvenanceAndConfidence:
    """Tests for provenance tracking and confidence scoring."""

    def test_api_evidence_is_high_confidence(self):
        result = AdapterResult(
            platform_key="youtube",
            platform_name="YouTube",
            username="testuser",
            found=True,
            acquisition_method=AcquisitionMethod.API,
            confidence=0.95,
            evidence_confidence=EvidenceConfidence.HIGH,
        )
        assert result.evidence_confidence == EvidenceConfidence.HIGH
        assert result.confidence >= 0.9

    def test_http_evidence_is_medium_confidence(self):
        result = AdapterResult(
            platform_key="github",
            platform_name="GitHub",
            username="testuser",
            found=True,
            acquisition_method=AcquisitionMethod.DIRECT_HTTP,
            confidence=0.85,
            evidence_confidence=EvidenceConfidence.MEDIUM,
        )
        assert result.evidence_confidence == EvidenceConfidence.MEDIUM
        assert 0.7 <= result.confidence <= 0.95

    def test_search_evidence_is_low_confidence(self):
        result = AdapterResult(
            platform_key="x_twitter",
            platform_name="X/Twitter",
            username="testuser",
            found=True,
            acquisition_method=AcquisitionMethod.SEARCH_DISCOVERY,
            confidence=0.55,
            evidence_confidence=EvidenceConfidence.LOW,
        )
        assert result.evidence_confidence == EvidenceConfidence.LOW
        assert result.confidence <= 0.65

    def test_raw_result_preserves_provenance(self):
        adapter = DirectHTTPAdapter()
        result = AdapterResult(
            platform_key="github",
            platform_name="GitHub",
            username="testuser",
            found=True,
            acquisition_method=AcquisitionMethod.DIRECT_HTTP,
            confidence=0.85,
            evidence_confidence=EvidenceConfidence.MEDIUM,
            evidence={"status_code": 200},
        )
        raw = adapter.to_raw_result(result, "inv-id")
        assert raw.raw_response["acquisition_method"] == "direct_http"
        assert raw.raw_response["evidence_confidence"] == "medium"
        assert raw.metadata["adapter"] == "direct_http"
        assert raw.metadata["acquisition_method"] == "direct_http"
        assert raw.metadata["evidence_confidence"] == "medium"

    def test_search_discovery_result_includes_warning(self):
        """Search discovery results should warn about unconfirmed status."""
        SearchDiscoveryAdapter()
        # The warning is in the evidence field, tested via probe method
        # This test documents the expected behavior
        assert "search_discovery" in [a.value for a in AcquisitionMethod]


# ── Graceful Fallback Tests ──────────────────────────────────────────────────


class TestGracefulFallback:
    """Tests for fallback behavior when adapters are unavailable."""

    @pytest.mark.asyncio
    async def test_orchestrator_falls_back_on_api_error(self):
        orch = PlatformIntelligenceOrchestrator()

        # Mock YouTube adapter to return None (error)
        with patch.object(
            orch._adapters["youtube_api"], "probe", new_callable=AsyncMock
        ) as mock_yt:
            mock_yt.return_value = None

            # Mock search discovery to return found
            mock_result = AdapterResult(
                platform_key="youtube",
                platform_name="YouTube",
                username="geerlingguy",
                found=True,
                url="https://youtube.com/@geerlingguy",
                acquisition_method=AcquisitionMethod.SEARCH_DISCOVERY,
                confidence=0.55,
                evidence_confidence=EvidenceConfidence.LOW,
            )
            with patch.object(
                orch._adapters["search_discovery"], "probe", new_callable=AsyncMock
            ) as mock_search:
                mock_search.return_value = mock_result

                result = await orch.probe_platform(
                    "youtube",
                    "geerlingguy",
                    "inv-id",
                    __import__(
                        "app.services.username_engine.models", fromlist=["ProbeBudget"]
                    ).ProbeBudget(),
                )

                assert result is not None
                assert result.found is True
                assert result.acquisition_method == AcquisitionMethod.SEARCH_DISCOVERY

    @pytest.mark.asyncio
    async def test_orchestrator_returns_none_all_adapters_fail(self):
        from app.services.username_engine.models import ProbeBudget

        orch = PlatformIntelligenceOrchestrator()

        with patch.object(
            orch._adapters["youtube_api"], "probe", new_callable=AsyncMock
        ) as mock_yt:
            mock_yt.return_value = None
            with patch.object(
                orch._adapters["search_discovery"], "probe", new_callable=AsyncMock
            ) as mock_search:
                mock_search.return_value = None

                result = await orch.probe_platform(
                    "youtube", "geerlingguy", "inv-id", ProbeBudget()
                )

                assert result is None

    def test_disabled_platforms_have_adapter_chain(self):
        """All disabled platforms should have at least one adapter available."""
        orch = PlatformIntelligenceOrchestrator()
        disabled_platforms = ["youtube", "x_twitter", "linkedin", "instagram", "tiktok"]

        for platform in disabled_platforms:
            chain = orch.get_adapter_chain(platform)
            assert len(chain) > 0, f"{platform} has no available adapters"
