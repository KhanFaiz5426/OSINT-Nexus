"""Username Intelligence Engine tests.

Tests for platform definitions, probe engine, and variation generation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.username_engine.models import PlatformDefinition, ProbeBudget, ProbeResult
from app.services.username_engine.platform_store import get_enabled_platforms, load_platforms
from app.services.username_engine.probe import UsernameProbeEngine
from app.services.username_variations import generate_probe_variations


class TestProbeBudget:
    """Tests for ProbeBudget model."""

    def test_default_budget(self):
        budget = ProbeBudget()
        assert budget.max_variations == 10
        assert budget.max_platforms == 20
        assert budget.max_total_requests == 200
        assert budget.timeout == 5.0

    def test_hard_upper_bounds_enforced(self):
        budget = ProbeBudget(
            max_variations=100,
            max_platforms=200,
            max_total_requests=5000,
        )
        assert budget.max_variations == 25  # ABSOLUTE_MAX_VARIATIONS
        assert budget.max_platforms == 50  # ABSOLUTE_MAX_PLATFORMS
        assert budget.max_total_requests == 1000  # ABSOLUTE_MAX_REQUESTS

    def test_within_bounds_passes(self):
        budget = ProbeBudget(max_variations=5, max_platforms=10, max_total_requests=50)
        assert budget.max_variations == 5
        assert budget.max_platforms == 10
        assert budget.max_total_requests == 50


class TestPlatformStore:
    """Tests for platform definition loading."""

    def test_load_platforms(self):
        platforms = load_platforms()
        assert len(platforms) > 0
        assert "github" in platforms
        assert "gitlab" in platforms
        assert "reddit" in platforms

    def test_platform_definition_structure(self):
        platforms = load_platforms()
        gh = platforms["github"]
        assert gh.key == "github"
        assert gh.name == "GitHub"
        assert "{username}" in gh.url_pattern
        assert gh.method == "GET"
        assert "status_codes" in gh.success_indicators
        assert "status_codes" in gh.failure_indicators

    def test_disabled_platforms(self):
        platforms = load_platforms()
        # Instagram should be disabled
        assert "instagram" in platforms
        assert platforms["instagram"].enabled is False

    def test_get_enabled_platforms(self):
        platforms = load_platforms()
        enabled = get_enabled_platforms(platforms)
        assert len(enabled) > 0
        # All returned platforms should be enabled
        for p in enabled:
            assert p.enabled is True
        # Disabled platforms should not appear
        enabled_keys = [p.key for p in enabled]
        assert "instagram" not in enabled_keys
        assert "x_twitter" not in enabled_keys

    def test_url_pattern_has_username_placeholder(self):
        platforms = load_platforms()
        for key, platform in platforms.items():
            assert "{username}" in platform.url_pattern, (
                f"Platform '{key}' missing {{username}} in url_pattern"
            )


class TestProbeVariations:
    """Tests for probe variation generation."""

    def test_original_first(self):
        variations = generate_probe_variations("mjkhan1400")
        assert variations[0] == "mjkhan1400"

    def test_single_word_variations(self):
        variations = generate_probe_variations("testuser")
        assert "testuser" in variations[0]
        assert len(variations) > 1
        # Should have suffix variations
        assert any(v.endswith("0") or v.endswith("1") or v.endswith("dev") for v in variations[1:])

    def test_multi_part_separator_variations(self):
        variations = generate_probe_variations("john.doe")
        assert "john.doe" in variations
        # Should have no-separator version
        assert "johndoe" in variations

    def test_max_variations_limit(self):
        variations = generate_probe_variations("testuser", max_variations=5)
        assert len(variations) <= 6  # original + 5

    def test_no_duplicates(self):
        variations = generate_probe_variations("testuser")
        assert len(variations) == len(set(variations))

    def test_empty_username(self):
        variations = generate_probe_variations("")
        assert len(variations) >= 1

    def test_probe_variations_are_subset_of_search_variations(self):
        """Probe variations should be a high-confidence subset."""
        from app.services.username_variations import generate_username_variations

        probe_vars = generate_probe_variations("mjkhan1400", max_variations=10)
        search_vars = generate_username_variations("mjkhan1400", max_variations=20)
        # Probe should have fewer variations
        assert len(probe_vars) <= len(search_vars)


class TestUsernameProbeEngine:
    """Tests for the probe engine."""

    def test_engine_initialization(self):
        engine = UsernameProbeEngine()
        assert engine.budget.max_variations == 10
        assert engine._requests_made == 0

    def test_engine_with_custom_budget(self):
        budget = ProbeBudget(max_variations=5, max_platforms=10)
        engine = UsernameProbeEngine(budget=budget)
        assert engine.budget.max_variations == 5
        assert engine.budget.max_platforms == 10

    def test_classify_response_success(self):
        engine = UsernameProbeEngine()
        platform = PlatformDefinition(
            key="test",
            name="Test",
            url_pattern="https://example.com/{username}",
            success_indicators={"status_codes": [200], "body_not_contains": ["not found"]},
            failure_indicators={"status_codes": [404]},
        )

        # Mock response
        response = MagicMock()
        response.status_code = 200
        response.text = "<html><title>John Doe</title></html>"
        response.url = "https://example.com/johndoe"

        result = engine._classify_response(
            platform, "johndoe", "johndoe", "https://example.com/johndoe", response
        )
        assert result.found is True
        assert result.confidence > 0.5

    def test_classify_response_failure_404(self):
        engine = UsernameProbeEngine()
        platform = PlatformDefinition(
            key="test",
            name="Test",
            url_pattern="https://example.com/{username}",
            success_indicators={"status_codes": [200]},
            failure_indicators={"status_codes": [404]},
        )

        response = MagicMock()
        response.status_code = 404
        response.text = "Not Found"
        response.url = "https://example.com/nobody"

        result = engine._classify_response(
            platform, "nobody", "nobody", "https://example.com/nobody", response
        )
        assert result.found is False

    def test_classify_response_body_negative_term(self):
        engine = UsernameProbeEngine()
        platform = PlatformDefinition(
            key="test",
            name="Test",
            url_pattern="https://example.com/{username}",
            success_indicators={
                "status_codes": [200],
                "body_not_contains": ["page not found"],
            },
            failure_indicators={"status_codes": [404]},
        )

        response = MagicMock()
        response.status_code = 200
        response.text = "<html>Page Not Found</html>"
        response.url = "https://example.com/johndoe"

        result = engine._classify_response(
            platform, "johndoe", "johndoe", "https://example.com/johndoe", response
        )
        assert result.found is False

    def test_to_raw_result(self):
        engine = UsernameProbeEngine()
        probe = ProbeResult(
            platform_key="github",
            platform_name="GitHub",
            username="johndoe",
            url="https://github.com/johndoe",
            found=True,
            status_code=200,
            confidence=0.85,
            evidence={"status_code": 200},
        )
        raw = engine._to_raw_result(probe, "test-investigation-id")
        assert raw.collector_name == "username_probe"
        assert raw.target == "johndoe"
        assert raw.confidence == 0.85
        assert raw.raw_response["found"] is True
        assert raw.raw_response["platform"] == "GitHub"

    @pytest.mark.asyncio
    async def test_probe_single_timeout(self):
        engine = UsernameProbeEngine(budget=ProbeBudget(max_total_requests=10))
        platform = PlatformDefinition(
            key="test",
            name="Test",
            url_pattern="https://example.com/{username}",
            success_indicators={"status_codes": [200]},
            failure_indicators={"status_codes": [404]},
            timeout=0.1,
        )

        with patch("app.services.username_engine.probe.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.request.side_effect = httpx.TimeoutException("timeout")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await engine._probe_single(platform, "johndoe", "johndoe", "test-inv-id")
            assert result is not None
            assert result.found is False
            assert result.error == "timeout"
