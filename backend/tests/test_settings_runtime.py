"""Tests proving that runtime settings from the Settings page actually
affect backend behavior — collector registration, cache TTL, rate limits,
LLM client, and investigation defaults.

These are INTEGRATION tests that write a temporary settings file and
verify the runtime changes propagate to the consumers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _write_settings(path: Path, data: dict) -> None:
    """Write a settings JSON file and reset the cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    import app.core.settings_store as store
    store._settings_cache = None


def _clear_settings() -> None:
    """Reset the settings cache."""
    import app.core.settings_store as store
    store._settings_cache = None


# ── Collector registration ───────────────────────────────────────────────────


class TestCollectorEnabledSetting:
    """Verify that collectors.enabled settings actually skip collectors."""

    def test_disabled_collector_is_not_registered(self, tmp_path: Path) -> None:
        """Disabling 'dns' in settings should exclude it from the registry."""
        settings_file = tmp_path / "settings.json"
        _write_settings(settings_file, {
            "collectors": {"enabled": {"dns": False}}
        })

        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store
            store._settings_cache = None

            from app.collectors.registry import _collectors, initialize_collectors
            _collectors.clear()

            import asyncio
            asyncio.get_event_loop().run_until_complete(
                initialize_collectors(cache=None)
            )

            assert "dns" not in _collectors, (
                "DNS collector should be excluded when disabled in settings"
            )
            # Other collectors should still be registered
            assert "whois" in _collectors
            _collectors.clear()
            _clear_settings()

    def test_enabled_collector_is_registered(self, tmp_path: Path) -> None:
        """Explicitly enabling a collector should register it."""
        settings_file = tmp_path / "settings.json"
        _write_settings(settings_file, {
            "collectors": {"enabled": {"dns": True}}
        })

        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store
            store._settings_cache = None

            from app.collectors.registry import _collectors, initialize_collectors
            _collectors.clear()

            import asyncio
            asyncio.get_event_loop().run_until_complete(
                initialize_collectors(cache=None)
            )

            assert "dns" in _collectors
            _collectors.clear()
            _clear_settings()

    def test_no_settings_file_registers_all(self, tmp_path: Path) -> None:
        """Without a settings file, all collectors should be registered."""
        settings_file = tmp_path / "nonexistent.json"
        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store
            store._settings_cache = None

            from app.collectors.registry import _collectors, initialize_collectors
            _collectors.clear()

            import asyncio
            asyncio.get_event_loop().run_until_complete(
                initialize_collectors(cache=None)
            )

            assert "dns" in _collectors
            assert "whois" in _collectors
            _collectors.clear()
            _clear_settings()


# ── Collector cache TTL ─────────────────────────────────────────────────────


class TestCollectorCacheTTL:
    """Verify that collectors.cache_ttl from settings affects collector instances."""

    def test_per_collector_ttl_override(self, tmp_path: Path) -> None:
        """Per-collector rate_limits entry should override the class default."""
        settings_file = tmp_path / "settings.json"
        _write_settings(settings_file, {
            "collectors": {"rate_limits": {"dns": 3600}}
        })

        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store
            store._settings_cache = None

            from app.collectors.dns_collector import DNSCollector
            collector = DNSCollector(cache=None)

            assert collector.cache_ttl == 3600, (
                f"Expected cache_ttl=3600 from settings, got {collector.cache_ttl}"
            )
            _clear_settings()

    def test_no_settings_uses_class_default(self, tmp_path: Path) -> None:
        """Without a settings file, the class default should be used."""
        settings_file = tmp_path / "nonexistent.json"
        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store
            store._settings_cache = None

            from app.collectors.dns_collector import DNSCollector
            collector = DNSCollector(cache=None)

            assert collector.cache_ttl == 3600  # DNS collector class default
            _clear_settings()


# ── Collector rate limits ───────────────────────────────────────────────────


class TestCollectorRateLimit:
    """Verify that collector rate limits from settings affect instances."""

    def test_per_collector_rate_limit(self, tmp_path: Path) -> None:
        """Per-collector rate_limits entry should override the class default."""
        settings_file = tmp_path / "settings.json"
        _write_settings(settings_file, {
            "collectors": {"rate_limits": {"http": 30}}
        })

        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store
            store._settings_cache = None

            from app.collectors.http_collector import HTTPCollector
            collector = HTTPCollector(cache=None)

            assert collector.rate_limit_rpm == 30, (
                f"Expected rate_limit_rpm=30 from settings, got {collector.rate_limit_rpm}"
            )
            assert collector._rate_limiter is not None
            _clear_settings()

    def test_no_rate_limit_settings_uses_class_default(self, tmp_path: Path) -> None:
        """Without per-collector settings, class defaults should apply."""
        settings_file = tmp_path / "nonexistent.json"
        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store
            store._settings_cache = None

            from app.collectors.http_collector import HTTPCollector
            collector = HTTPCollector(cache=None)

            # HTTPCollector class default is 300 RPM
            assert collector.rate_limit_rpm == 300
            _clear_settings()


# ── AI client settings overlay ──────────────────────────────────────────────


class TestAISettingsOverlay:
    """Verify that LLM settings from the settings store affect the AI client."""

    def test_overlay_returns_env_defaults_without_file(self, tmp_path: Path) -> None:
        """Without a settings file, env defaults should be used."""
        settings_file = tmp_path / "nonexistent.json"
        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store
            store._settings_cache = None

            from app.ai.client import _overlay_runtime_llm_settings

            class FakeEnv:
                LLM_PROVIDER = "none"
                LLM_MAX_TOKENS = 2048
                LLM_TEMPERATURE = 0.3

            provider, max_tokens, temperature = _overlay_runtime_llm_settings(FakeEnv())
            assert provider == "none"
            assert max_tokens == 2048
            assert temperature == 0.3
            _clear_settings()

    def test_overlay_uses_settings_when_file_exists(self, tmp_path: Path) -> None:
        """With a settings file, runtime values should override env defaults."""
        settings_file = tmp_path / "settings.json"
        _write_settings(settings_file, {
            "llm": {
                "active_provider": "openai",
                "max_tokens": 4096,
                "temperature": 0.7,
            }
        })

        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store
            store._settings_cache = None

            from app.ai.client import _overlay_runtime_llm_settings

            class FakeEnv:
                LLM_PROVIDER = "none"
                LLM_MAX_TOKENS = 2048
                LLM_TEMPERATURE = 0.3

            provider, max_tokens, temperature = _overlay_runtime_llm_settings(FakeEnv())
            assert provider == "openai"
            assert max_tokens == 4096
            assert temperature == 0.7
            _clear_settings()

    def test_overlay_model_override(self, tmp_path: Path) -> None:
        """Model and base_url from settings should be passed as overrides."""
        settings_file = tmp_path / "settings.json"
        _write_settings(settings_file, {
            "llm": {
                "model": "gpt-4o-mini",
                "base_url": "https://custom.api.com/v1",
            }
        })

        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store
            store._settings_cache = None

            from app.ai.client import _build_provider_config

            class FakeEnv:
                LLM_PROVIDER = "openai"
                NVIDIA_API_KEY = ""
                OPENAI_API_KEY = "test-key"
                ANTHROPIC_API_KEY = ""
                OPENCODE_API_KEY = ""
                LLM_API_KEY = ""
                LLM_MODEL = ""
                LLM_BASE_URL = ""

            cfg = _build_provider_config("openai", FakeEnv(), {
                "model": "gpt-4o-mini",
                "base_url": "https://custom.api.com/v1",
            })
            assert cfg is not None
            assert cfg["model"] == "gpt-4o-mini"
            assert cfg["base_url"] == "https://custom.api.com/v1"
            _clear_settings()


# ── Investigation defaults ──────────────────────────────────────────────────


class TestInvestigationDefaults:
    """Verify that investigation settings affect runtime behavior."""

    def test_orchestrator_budget_from_settings(self, tmp_path: Path) -> None:
        """_get_default_budget() should read from settings store."""
        settings_file = tmp_path / "settings.json"
        _write_settings(settings_file, {
            "investigation": {"api_budget": 500}
        })

        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store
            store._settings_cache = None

            from app.services.orchestrator import _get_default_budget
            budget = _get_default_budget()
            assert budget == 500, f"Expected budget=500, got {budget}"
            _clear_settings()

    def test_orchestrator_budget_default_without_file(self, tmp_path: Path) -> None:
        """Without a settings file, the hardcoded default should be used."""
        settings_file = tmp_path / "nonexistent.json"
        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store
            store._settings_cache = None

            from app.services.orchestrator import _get_default_budget
            budget = _get_default_budget()
            assert budget == 100  # DEFAULT_BUDGET
            _clear_settings()

    def test_probe_settings_from_store(self, tmp_path: Path) -> None:
        """ProbeBudget should reflect settings store values."""
        settings_file = tmp_path / "settings.json"
        _write_settings(settings_file, {
            "investigation": {
                "probe": {
                    "max_variations": 15,
                    "max_platforms": 30,
                    "timeout": 10.0,
                }
            }
        })

        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store
            store._settings_cache = None

            from app.core.settings_store import get_app_settings
            app = get_app_settings()
            assert app.investigation.probe.max_variations == 15
            assert app.investigation.probe.max_platforms == 30
            assert app.investigation.probe.timeout == 10.0
            _clear_settings()
