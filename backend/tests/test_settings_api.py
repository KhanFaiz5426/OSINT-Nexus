"""Tests for settings API endpoints and settings_store module."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.settings_store import (
    AppSettings,
    GeneralSettings,
    InvestigationDefaults,
    LLMProviderSettings,
    ProbeSettings,
    _deep_merge,
    _load_from_file,
    _save_to_file,
    get_app_settings,
    reload_app_settings,
    update_app_settings,
)
from app.db.client import close_pool, reset_pool
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def _reset_db():
    reset_pool()
    yield
    await close_pool()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def tmp_settings_file(tmp_path):
    """Provide a temporary settings file path and patch the module."""
    settings_file = tmp_path / "settings.json"
    with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
        import app.core.settings_store as store

        store._settings_cache = None
        yield settings_file
        store._settings_cache = None


class TestSettingsModels:
    """Test Pydantic models for settings."""

    def test_general_defaults(self):
        s = GeneralSettings()
        assert s.default_depth == "standard"
        assert s.max_concurrent_investigations == 5
        assert s.auto_save_reports is True

    def test_general_validation_max_concurrent(self):
        with pytest.raises(Exception):
            GeneralSettings(max_concurrent_investigations=0)
        with pytest.raises(Exception):
            GeneralSettings(max_concurrent_investigations=25)

    def test_probe_defaults(self):
        s = ProbeSettings()
        assert s.max_variations == 10
        assert s.max_platforms == 20
        assert s.max_total_requests == 200
        assert s.timeout == 5.0

    def test_probe_validation_timeout(self):
        with pytest.raises(Exception):
            ProbeSettings(timeout=0.5)
        with pytest.raises(Exception):
            ProbeSettings(timeout=50.0)

    def test_llm_validation_temperature(self):
        with pytest.raises(Exception):
            LLMProviderSettings(temperature=-0.1)
        with pytest.raises(Exception):
            LLMProviderSettings(temperature=2.5)

    def test_investigation_validation_budget(self):
        with pytest.raises(Exception):
            InvestigationDefaults(api_budget=5)
        with pytest.raises(Exception):
            InvestigationDefaults(api_budget=2000)

    def test_app_settings_defaults(self):
        s = AppSettings()
        assert s.general.default_depth == "standard"
        assert s.llm.active_provider == "ollama"
        assert s.investigation.probe.max_variations == 10
        assert s.version == "0.1.0"


class TestSettingsFilePersistence:
    """Test JSON file read/write."""

    def test_save_and_load(self, tmp_path):
        data = {"general": {"auto_save_reports": False}}
        settings_file = tmp_path / "settings.json"
        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            _save_to_file(data)
            loaded = _load_from_file()
            assert loaded["general"]["auto_save_reports"] is False

    def test_load_missing_file_returns_empty(self, tmp_path):
        settings_file = tmp_path / "nonexistent.json"
        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            loaded = _load_from_file()
            assert loaded == {}

    def test_load_corrupt_file_returns_empty(self, tmp_path):
        settings_file = tmp_path / "bad.json"
        settings_file.write_text("{invalid json", encoding="utf-8")
        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            loaded = _load_from_file()
            assert loaded == {}

    def test_save_creates_parent_directory(self, tmp_path):
        nested = tmp_path / "sub" / "dir" / "settings.json"
        with patch("app.core.settings_store.SETTINGS_FILE", nested):
            _save_to_file({"general": {}})
            assert nested.exists()

    def test_get_app_settings_returns_defaults_when_no_file(self, tmp_path):
        settings_file = tmp_path / "nope.json"
        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            s = get_app_settings()
            assert s.general.default_depth == "standard"

    def test_update_app_settings_persists(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store

            store._settings_cache = None
            updated = update_app_settings({"general": {"auto_save_reports": False}})
            assert updated.general.auto_save_reports is False
            # Verify on disk
            disk = json.loads(settings_file.read_text(encoding="utf-8"))
            assert disk["general"]["auto_save_reports"] is False
            store._settings_cache = None

    def test_reload_app_settings_clears_cache(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        with patch("app.core.settings_store.SETTINGS_FILE", settings_file):
            import app.core.settings_store as store

            store._settings_cache = None
            # Write initial
            _save_to_file({"general": {"auto_save_reports": True}})
            s1 = get_app_settings()
            assert s1.general.auto_save_reports is True
            # Overwrite file
            _save_to_file({"general": {"auto_save_reports": False}})
            s2 = reload_app_settings()
            assert s2.general.auto_save_reports is False
            store._settings_cache = None


class TestDeepMerge:
    """Test the deep merge utility."""

    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        _deep_merge(base, override)
        assert base == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}}
        override = {"a": {"y": 99}}
        _deep_merge(base, override)
        assert base == {"a": {"x": 1, "y": 99}}

    def test_deep_nested_merge(self):
        base = {"a": {"b": {"c": 1, "d": 2}}}
        override = {"a": {"b": {"d": 99}}}
        _deep_merge(base, override)
        assert base == {"a": {"b": {"c": 1, "d": 99}}}

    def test_override_replaces_non_dict(self):
        base = {"a": [1, 2]}
        override = {"a": [3]}
        _deep_merge(base, override)
        assert base == {"a": [3]}


class TestSettingsAPIEndpoints:
    """Test HTTP API endpoints for settings."""

    @pytest.mark.anyio
    async def test_get_settings_returns_200(self, client: AsyncClient):
        response = await client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()
        assert "settings" in data
        assert "api_keys" in data
        assert "service_health" in data
        assert "restart_required" in data

    @pytest.mark.anyio
    async def test_get_settings_structure(self, client: AsyncClient):
        response = await client.get("/api/v1/settings")
        data = response.json()
        settings = data["settings"]
        assert "general" in settings
        assert "llm" in settings
        assert "collectors" in settings
        assert "investigation" in settings
        assert settings["general"]["default_depth"] == "standard"

    @pytest.mark.anyio
    async def test_get_settings_api_keys_masked(self, client: AsyncClient):
        response = await client.get("/api/v1/settings")
        data = response.json()
        api_keys = data["api_keys"]
        for _key, val in api_keys.items():
            assert isinstance(val, bool)

    @pytest.mark.anyio
    async def test_put_settings_general(self, client: AsyncClient):
        response = await client.put(
            "/api/v1/settings",
            json={"general": {"auto_save_reports": False}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"].startswith("Settings updated")
        assert data["settings"]["general"]["auto_save_reports"] is False

    @pytest.mark.anyio
    async def test_put_settings_llm(self, client: AsyncClient):
        response = await client.put(
            "/api/v1/settings",
            json={"llm": {"temperature": 0.7}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["settings"]["llm"]["temperature"] == 0.7

    @pytest.mark.anyio
    async def test_put_settings_probe(self, client: AsyncClient):
        response = await client.put(
            "/api/v1/settings",
            json={"investigation": {"probe": {"max_variations": 15}}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["settings"]["investigation"]["probe"]["max_variations"] == 15

    @pytest.mark.anyio
    async def test_put_settings_restart_required_detection(self, client: AsyncClient):
        response = await client.put(
            "/api/v1/settings",
            json={"llm": {"active_provider": "openai"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert "llm.active_provider" in data["restart_required"]

    @pytest.mark.anyio
    async def test_put_settings_no_body_returns_400(self, client: AsyncClient):
        response = await client.put("/api/v1/settings", json={})
        assert response.status_code == 400

    @pytest.mark.anyio
    async def test_put_settings_invalid_value_returns_422(self, client: AsyncClient):
        response = await client.put(
            "/api/v1/settings",
            json={"general": {"max_concurrent_investigations": 0}},
        )
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_post_reload_returns_200(self, client: AsyncClient):
        response = await client.post("/api/v1/settings/reload")
        assert response.status_code == 200
        data = response.json()
        assert "settings" in data
        assert "api_keys" in data

    @pytest.mark.anyio
    async def test_settings_persist_across_get_calls(self, client: AsyncClient):
        # Update
        await client.put(
            "/api/v1/settings",
            json={"general": {"auto_save_reports": False}},
        )
        # Verify persisted
        response = await client.get("/api/v1/settings")
        data = response.json()
        assert data["settings"]["general"]["auto_save_reports"] is False
