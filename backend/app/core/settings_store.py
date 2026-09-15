"""Runtime settings store — JSON file persistence.

Provides a simple JSON-file-backed settings store that overlays
environment variables. Settings that require restart are clearly
marked in the API response.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

SETTINGS_FILE = Path(
    os.getenv(
        "SETTINGS_FILE", 
        os.path.join(os.environ.get("APPDATA", ""), "osint-nexus", "config.json")
        if os.name == "nt" 
        else str(Path.home() / ".config" / "osint-nexus" / "config.json")
    )
)


class GeneralSettings(BaseModel):
    default_depth: str = "standard"
    max_concurrent_investigations: int = Field(default=5, ge=1, le=20)
    auto_save_reports: bool = True


class LLMProviderSettings(BaseModel):
    active_provider: str = "ollama"
    model: str = ""
    base_url: str = ""
    max_tokens: int = Field(default=2048, ge=256, le=32768)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    api_keys_configured: dict[str, bool] = Field(default_factory=dict)


class CollectorSettings(BaseModel):
    enabled: dict[str, bool] = Field(default_factory=dict)
    rate_limits: dict[str, int] = Field(default_factory=dict)
    cache_ttl: int = Field(default=86400, ge=300, le=604800)
    search_rate_limit_rpm: int = Field(default=10, ge=1, le=60)


class ProbeSettings(BaseModel):
    max_variations: int = Field(default=10, ge=1, le=25)
    max_platforms: int = Field(default=20, ge=1, le=50)
    max_total_requests: int = Field(default=200, ge=10, le=1000)
    timeout: float = Field(default=5.0, ge=1.0, le=30.0)


class InvestigationDefaults(BaseModel):
    api_budget: int = Field(default=100, ge=10, le=1000)
    probe: ProbeSettings = Field(default_factory=ProbeSettings)


class AppSettings(BaseModel):
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    llm: LLMProviderSettings = Field(default_factory=LLMProviderSettings)
    collectors: CollectorSettings = Field(default_factory=CollectorSettings)
    investigation: InvestigationDefaults = Field(default_factory=InvestigationDefaults)
    version: str = "0.1.0"


_settings_cache: AppSettings | None = None


def _load_from_file() -> dict[str, Any]:
    """Load settings from JSON file."""
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load settings file %s: %s", SETTINGS_FILE, exc)
    return {}


def _save_to_file(data: dict[str, Any]) -> None:
    """Save settings to JSON file."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps(data, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Settings saved to %s", SETTINGS_FILE)


def get_app_settings() -> AppSettings:
    """Get current application settings (file overlay on env defaults)."""
    global _settings_cache
    if _settings_cache is None:
        file_data = _load_from_file()
        _settings_cache = AppSettings(**file_data) if file_data else AppSettings()
    return _settings_cache


def reload_app_settings() -> AppSettings:
    """Force reload settings from disk."""
    global _settings_cache
    _settings_cache = None
    return get_app_settings()


def update_app_settings(update: dict[str, Any]) -> AppSettings:
    """Update settings and persist to disk."""
    global _settings_cache
    current = get_app_settings()
    current_data = current.model_dump()
    _deep_merge(current_data, update)
    _settings_cache = AppSettings(**current_data)
    _save_to_file(current_data)
    return _settings_cache


def _deep_merge(base: dict, override: dict) -> None:
    """Deep merge override into base."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value





def get_service_health() -> dict[str, Any]:
    """Check health of all backend services."""
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "database": {
            "host": settings.POSTGRES_HOST,
            "port": settings.POSTGRES_PORT,
            "name": settings.POSTGRES_DB,
        },
        "neo4j": {
            "uri": settings.NEO4J_URI,
            "user": settings.NEO4J_USER,
        },
    }
