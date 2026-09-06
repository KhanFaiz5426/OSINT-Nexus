"""API routes — System configuration status.

Returns read-only configuration status for the frontend Settings panel.
No secrets or API keys are exposed.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class CollectorStatus(BaseModel):
    """Status of a single OSINT collector."""

    name: str
    version: str
    available: bool
    api_key_configured: bool
    requires_api_key: bool
    supported_target_types: list[str]


class LLMProviderStatus(BaseModel):
    """Status of an LLM provider."""

    name: str
    configured: bool
    selected: bool


class ConfigStatusResponse(BaseModel):
    """System configuration status (no secrets exposed)."""

    app_version: str
    llm_provider: str
    llm_configured: bool
    collectors: list[CollectorStatus]
    llm_providers: list[LLMProviderStatus]


@router.get("/config/status", response_model=ConfigStatusResponse)
async def get_config_status() -> ConfigStatusResponse:
    """Return system configuration status without exposing secrets.

    Shows which collectors are available, which LLM provider is selected,
    and whether API keys are configured — but never the actual key values.
    """
    from app.collectors.registry import get_all_collectors
    from app.core.config import get_settings

    settings = get_settings()

    # Collector statuses
    collectors = []
    all_collectors = get_all_collectors()
    for name in sorted(all_collectors.keys()):
        collector = all_collectors[name]
        collectors.append(
            CollectorStatus(
                name=collector.name,
                version=collector.version,
                available=True,
                api_key_configured=(
                    not collector.requires_api_key
                    or collector._is_api_key_available()
                ),
                requires_api_key=collector.requires_api_key,
                supported_target_types=[t.value for t in collector.supported_target_types],
            )
        )

    # LLM provider statuses
    providers = [
        LLMProviderStatus(
            name="opencode",
            configured=bool(settings.OPENCODE_API_KEY),
            selected=settings.LLM_PROVIDER == "opencode",
        ),
        LLMProviderStatus(
            name="nvidia",
            configured=bool(settings.NVIDIA_API_KEY),
            selected=settings.LLM_PROVIDER == "nvidia",
        ),
        LLMProviderStatus(
            name="openai",
            configured=bool(settings.OPENAI_API_KEY),
            selected=settings.LLM_PROVIDER == "openai",
        ),
        LLMProviderStatus(
            name="anthropic",
            configured=bool(settings.ANTHROPIC_API_KEY),
            selected=settings.LLM_PROVIDER == "anthropic",
        ),
        LLMProviderStatus(
            name="ollama",
            configured=settings.LLM_PROVIDER == "ollama",
            selected=settings.LLM_PROVIDER == "ollama",
        ),
    ]

    llm_configured = settings.LLM_PROVIDER not in ("none", "")

    return ConfigStatusResponse(
        app_version=settings.APP_VERSION,
        llm_provider=settings.LLM_PROVIDER,
        llm_configured=llm_configured,
        collectors=collectors,
        llm_providers=providers,
    )
