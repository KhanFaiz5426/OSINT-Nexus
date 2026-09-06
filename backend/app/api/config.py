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


class CollectorHealthDetail(BaseModel):
    """Detailed health information for a collector."""

    name: str
    version: str
    available: bool
    api_key_configured: bool
    rate_limit_rpm: int
    cache_ttl_seconds: int
    last_error: str = ""
    requires_api_key: bool
    supported_target_types: list[str]


class CollectorHealthResponse(BaseModel):
    """Response for collector health endpoint."""

    collectors: list[CollectorHealthDetail]
    total_collectors: int
    available_collectors: int


class RateLimitStatus(BaseModel):
    """Rate limit status for a single collector."""

    name: str
    rate_limit_rpm: int
    available_tokens: float
    is_limited: bool


class RateLimitResponse(BaseModel):
    """Response for rate limit endpoint."""

    collectors: list[RateLimitStatus]


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


@router.get("/collectors/health", response_model=CollectorHealthResponse)
async def get_collector_health() -> CollectorHealthResponse:
    """Return detailed health status for all collectors.

    Includes rate limit state, cache status, and last error information.
    """
    from app.collectors.registry import get_all_collectors

    all_collectors = get_all_collectors()
    health_details = []

    for name in sorted(all_collectors.keys()):
        collector = all_collectors[name]
        health = await collector.health_check()

        # Get rate limiter status
        rate_limit_rpm = 0
        if collector._rate_limiter:
            rate_limit_rpm = collector.rate_limit_rpm

        health_details.append(
            CollectorHealthDetail(
                name=health["name"],
                version=health["version"],
                available=health["available"],
                api_key_configured=health["api_key_configured"],
                rate_limit_rpm=rate_limit_rpm,
                cache_ttl_seconds=health.get("cache_ttl_seconds", 0),
                last_error=health.get("last_error", ""),
                requires_api_key=collector.requires_api_key,
                supported_target_types=[t.value for t in collector.supported_target_types],
            )
        )

    available_count = sum(1 for h in health_details if h.available)

    return CollectorHealthResponse(
        collectors=health_details,
        total_collectors=len(health_details),
        available_collectors=available_count,
    )


@router.get("/collectors/rate-limits", response_model=RateLimitResponse)
async def get_rate_limits() -> RateLimitResponse:
    """Return rate limit status for all collectors.

    Shows current token availability and whether collectors are throttled.
    """
    from app.collectors.registry import get_all_collectors

    all_collectors = get_all_collectors()
    rate_limit_statuses = []

    for name in sorted(all_collectors.keys()):
        collector = all_collectors[name]

        rate_limit_rpm = collector.rate_limit_rpm
        available_tokens = 0.0
        is_limited = False

        if collector._rate_limiter:
            available_tokens = collector._rate_limiter.available_tokens
            is_limited = available_tokens < 1.0

        rate_limit_statuses.append(
            RateLimitStatus(
                name=collector.name,
                rate_limit_rpm=rate_limit_rpm,
                available_tokens=available_tokens,
                is_limited=is_limited,
            )
        )

    return RateLimitResponse(collectors=rate_limit_statuses)
