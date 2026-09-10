"""Settings API — application-level configuration management.

Provides endpoints for reading and updating application settings.
Secrets are never exposed; only masked status is returned.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from app.core.settings_store import (
    AppSettings,
    get_app_settings,
    get_masked_api_keys,
    get_service_health,
    reload_app_settings,
    update_app_settings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsResponse(BaseModel):
    settings: AppSettings
    api_keys: dict[str, bool]
    service_health: dict[str, Any]
    restart_required: list[str] = Field(default_factory=list)


class SettingsUpdateRequest(BaseModel):
    general: dict[str, Any] | None = None
    llm: dict[str, Any] | None = None
    collectors: dict[str, Any] | None = None
    investigation: dict[str, Any] | None = None


class SettingsUpdateResponse(BaseModel):
    message: str
    settings: AppSettings
    restart_required: list[str] = Field(default_factory=list)


# Settings that require restart to take effect
_RESTART_REQUIRED_FIELDS = {
    "llm.active_provider",
    "llm.model",
    "llm.base_url",
    "llm.api_keys_configured",
}


def _detect_restart_needed(update: dict[str, Any], prefix: str = "") -> list[str]:
    """Check which updated fields require restart."""
    needed = []
    for key, value in update.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            needed.extend(_detect_restart_needed(value, full_key))
        elif full_key in _RESTART_REQUIRED_FIELDS:
            needed.append(full_key)
    return needed


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """Get current application settings with status information."""
    settings = get_app_settings()
    api_keys = get_masked_api_keys()
    health = get_service_health()

    # Inject runtime API key status into LLM settings
    settings.llm.api_keys_configured = api_keys

    return SettingsResponse(
        settings=settings,
        api_keys=api_keys,
        service_health=health,
    )


@router.put("", response_model=SettingsUpdateResponse)
async def put_settings(request: SettingsUpdateRequest) -> SettingsUpdateResponse:
    """Update application settings. Persists to disk."""
    update: dict[str, Any] = {}
    if request.general is not None:
        update["general"] = request.general
    if request.llm is not None:
        update["llm"] = request.llm
    if request.collectors is not None:
        update["collectors"] = request.collectors
    if request.investigation is not None:
        update["investigation"] = request.investigation

    if not update:
        raise HTTPException(status_code=400, detail="No settings provided")

    restart_needed = _detect_restart_needed(update)
    try:
        updated = update_app_settings(update)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    return SettingsUpdateResponse(
        message="Settings updated"
        + (" (restart required for some changes)" if restart_needed else ""),
        settings=updated,
        restart_required=restart_needed,
    )


@router.post("/reload", response_model=SettingsResponse)
async def post_reload() -> SettingsResponse:
    """Force reload settings from disk."""
    settings = reload_app_settings()
    api_keys = get_masked_api_keys()
    health = get_service_health()
    settings.llm.api_keys_configured = api_keys

    return SettingsResponse(
        settings=settings,
        api_keys=api_keys,
        service_health=health,
    )
