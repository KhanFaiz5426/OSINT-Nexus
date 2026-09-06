"""AI LLM client — provider-agnostic LLM integration.

Supports multiple providers via a unified interface:
- NVIDIA API (OpenAI-compatible endpoint, primary hosted provider)
- OpenAI (optional)
- Anthropic (optional)
- Ollama (optional local provider)

The client produces an async callable matching the llm_call_fn signature
expected by the planner and analyzer: (messages: list[dict]) -> str.

When no provider is configured, the client returns None, which causes
the planner and analyzer to degrade gracefully with deterministic defaults.

Security: All LLM output is untrusted. The client only returns raw text;
validation is handled by the caller (validator.py).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ── Provider implementations ─────────────────────────────────────────────────


async def _call_nvidia(
    messages: list[dict[str, str]],
    *,
    api_key: str,
    model: str,
    base_url: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Call NVIDIA API (OpenAI-compatible endpoint) with retry on transient errors."""
    import asyncio

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    max_retries = 3
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.debug(
                    "LLM Request: POST %s (model=%s, max_tokens=%s, attempt=%d/%d)",
                    url, model, max_tokens, attempt + 1, max_retries,
                )
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.debug("LLM Response (%d chars)", len(content))
                    return content
                # Retry on transient errors
                if resp.status_code in (429, 500, 502, 503):
                    wait = 2 ** attempt * 3  # 3s, 6s, 12s
                    logger.warning(
                        "LLM transient error %s (attempt %d/%d), retrying in %ds. Body: %.200s",
                        resp.status_code, attempt + 1, max_retries, wait,
                        resp.text,
                    )
                    await asyncio.sleep(wait)
                    last_exc = httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp,
                    )
                    continue
                # Non-retryable error — log and raise immediately
                logger.error(
                    "LLM Error Response: %s - %.500s",
                    resp.status_code, resp.text,
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 3
                logger.warning(
                    "LLM request error (attempt %d/%d): %s: %s, retrying in %ds",
                    attempt + 1, max_retries, type(exc).__name__, exc, wait,
                )
                await asyncio.sleep(wait)
            else:
                raise

    if last_exc:
        raise last_exc
    raise RuntimeError("LLM call failed after all retries")


async def _call_openai(
    messages: list[dict[str, str]],
    *,
    api_key: str,
    model: str,
    base_url: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Call OpenAI-compatible API with retry on rate limit."""
    import asyncio

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    max_retries = 3
    for attempt in range(max_retries):
        async with httpx.AsyncClient(timeout=60.0) as client:
            logger.debug("LLM Request (OpenAI): POST %s (payload: %s)", url, {k: v for k, v in payload.items() if k != "messages"})
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200 and resp.status_code != 429:
                logger.error("LLM Error Response (OpenAI): %s - %s", resp.status_code, resp.text)
            if resp.status_code == 429:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                logger.warning("Rate limited (429), retrying in %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            content_str = data["choices"][0]["message"]["content"]
            logger.debug("LLM Response (OpenAI) (%d chars)", len(content_str))
            return content_str

    raise httpx.HTTPStatusError("Rate limit exceeded after retries", request=resp.request, response=resp)


async def _call_anthropic(
    messages: list[dict[str, str]],
    *,
    api_key: str,
    model: str,
    base_url: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Call Anthropic Messages API."""
    url = f"{base_url.rstrip('/')}/v1/messages"

    # Anthropic uses a different message format.
    system_msg = ""
    user_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_msg = msg["content"]
        else:
            user_messages.append(msg)

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": user_messages,
    }
    if system_msg:
        payload["system"] = system_msg

    async with httpx.AsyncClient(timeout=60.0) as client:
        logger.debug("LLM Request (Anthropic): POST %s (payload: %s)", url, {k: v for k, v in payload.items() if k != "messages" and k != "system"})
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            logger.error("LLM Error Response (Anthropic): %s - %s", resp.status_code, resp.text)
        resp.raise_for_status()
        data = resp.json()
        content_str = data["content"][0]["text"]
        logger.debug("LLM Response (Anthropic) (%d chars)", len(content_str))
        return content_str


async def _call_ollama(
    messages: list[dict[str, str]],
    *,
    model: str,
    base_url: str,
    max_tokens: int,
    temperature: float,
    **_kwargs: Any,
) -> str:
    """Call Ollama API (OpenAI-compatible endpoint)."""
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        logger.debug("LLM Request (Ollama): POST %s (payload: %s)", url, {k: v for k, v in payload.items() if k != "messages"})
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            logger.error("LLM Error Response (Ollama): %s - %s", resp.status_code, resp.text)
        resp.raise_for_status()
        data = resp.json()
        content_str = data["choices"][0]["message"]["content"]
        logger.debug("LLM Response (Ollama) (%d chars)", len(content_str))
        return content_str


# ── Provider dispatch ────────────────────────────────────────────────────────

PROVIDER_CALLERS: dict[str, Any] = {
    "nvidia": _call_nvidia,
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "ollama": _call_ollama,
    "opencode": _call_openai,
}

PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "model": "claude-sonnet-4-20250514",
    },
    "ollama": {
        "base_url": "http://localhost:11434",
        "model": "llama3.1",
    },
    "opencode": {
        "base_url": "https://opencode.ai/zen/v1",
        "model": "mimo-v2.5-free",
    },
}


def _mask_key(key: str) -> str:
    """Mask an API key for safe logging — show only last 4 chars."""
    if not key or len(key) < 8:
        return "***"
    return f"***{key[-4:]}"


def _build_provider_config(
    provider: str, settings: Any,
) -> dict[str, Any] | None:
    """Build config dict for a provider, or None if not configured."""
    caller = PROVIDER_CALLERS.get(provider)
    if caller is None:
        return None

    defaults = PROVIDER_DEFAULTS.get(provider, {})

    # Resolve API key
    if provider == "nvidia":
        api_key = settings.NVIDIA_API_KEY or settings.LLM_API_KEY
    elif provider == "openai":
        api_key = settings.OPENAI_API_KEY or settings.LLM_API_KEY
    elif provider == "anthropic":
        api_key = settings.ANTHROPIC_API_KEY or settings.LLM_API_KEY
    elif provider == "opencode":
        api_key = settings.OPENCODE_API_KEY or settings.LLM_API_KEY
    else:
        api_key = settings.LLM_API_KEY

    if provider in ("nvidia", "openai", "anthropic", "opencode") and not api_key:
        return None

    model = defaults.get("model", "") if provider != settings.LLM_PROVIDER.lower().strip() else (settings.LLM_MODEL or defaults.get("model", ""))
    base_url = defaults.get("base_url", "") if provider != settings.LLM_PROVIDER.lower().strip() else (settings.LLM_BASE_URL or defaults.get("base_url", ""))

    if provider == "ollama" and not base_url:
        base_url = "http://localhost:11434"

    return {
        "caller": caller,
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
        "provider": provider,
    }


# Preferred fallback order
_FALLBACK_ORDER = ["nvidia", "opencode", "openai", "anthropic", "ollama"]


def get_llm_call_fn() -> Any:
    """Build and return an async LLM callable based on configured provider.

    Returns an async callable (messages) -> str, or None if no provider
    is configured or the provider's API key is missing.

    When the primary provider fails, automatically falls back to the next
    available provider with valid credentials.

    The returned callable is suitable for passing as llm_call_fn to
    plan_pivots_with_ai() and analyze_investigation().
    """
    settings = get_settings()
    primary = settings.LLM_PROVIDER.lower().strip()

    if not primary or primary == "none":
        logger.info("No LLM provider configured; AI features disabled")
        return None

    # Build provider chain: primary first, then fallbacks
    provider_configs: list[dict[str, Any]] = []

    # Primary provider
    primary_cfg = _build_provider_config(primary, settings)
    if primary_cfg:
        provider_configs.append(primary_cfg)
    else:
        logger.warning(
            "Primary LLM provider '%s' not usable (missing key); checking fallbacks",
            primary,
        )

    # Add fallback providers
    for fb_provider in _FALLBACK_ORDER:
        if fb_provider == primary:
            continue
        fb_cfg = _build_provider_config(fb_provider, settings)
        if fb_cfg:
            provider_configs.append(fb_cfg)

    if not provider_configs:
        logger.info("No LLM providers available; AI features disabled")
        return None

    max_tokens = settings.LLM_MAX_TOKENS
    temperature = settings.LLM_TEMPERATURE

    logger.info(
        "LLM provider chain: %s",
        " → ".join(
            f"{c['provider']}({c['model']}, key={_mask_key(c['api_key'])})"
            for c in provider_configs
        ),
    )

    async def _llm_call(messages: list[dict[str, str]]) -> str:
        last_exc: Exception | None = None
        for cfg in provider_configs:
            try:
                result = await cfg["caller"](
                    messages,
                    api_key=cfg["api_key"],
                    model=cfg["model"],
                    base_url=cfg["base_url"],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return result
            except Exception as exc:
                logger.warning(
                    "LLM provider '%s' failed: %s: %s — trying next",
                    cfg["provider"],
                    type(exc).__name__,
                    str(exc)[:200],
                )
                last_exc = exc
                continue

        # All providers failed
        raise last_exc or RuntimeError("All LLM providers failed")

    return _llm_call
