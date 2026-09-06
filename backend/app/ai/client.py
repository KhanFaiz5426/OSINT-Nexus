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
    """Call NVIDIA API (OpenAI-compatible endpoint)."""
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

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


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
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 429:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                logger.warning("Rate limited (429), retrying in %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

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
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]


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
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


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


def get_llm_call_fn() -> Any:
    """Build and return an async LLM callable based on configured provider.

    Returns an async callable (messages) -> str, or None if no provider
    is configured or the provider's API key is missing.

    The returned callable is suitable for passing as llm_call_fn to
    plan_pivots_with_ai() and analyze_investigation().
    """
    settings = get_settings()
    provider = settings.LLM_PROVIDER.lower().strip()

    if not provider or provider == "none":
        logger.info("No LLM provider configured; AI features disabled")
        return None

    caller = PROVIDER_CALLERS.get(provider)
    if caller is None:
        logger.warning("Unknown LLM provider '%s'; AI features disabled", provider)
        return None

    # Resolve provider-specific defaults.
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    
    # Try provider specific key, then fallback to LLM_API_KEY
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

    model = settings.LLM_MODEL or defaults.get("model", "")
    base_url = settings.LLM_BASE_URL or defaults.get("base_url", "")
    max_tokens = settings.LLM_MAX_TOKENS
    temperature = settings.LLM_TEMPERATURE

    # Validate that required credentials are present.
    if provider in ("nvidia", "openai", "anthropic", "opencode") and not api_key:
        logger.info(
            "LLM provider '%s' configured but API key is missing; AI features disabled",
            provider,
        )
        return None

    if provider == "ollama" and not base_url:
        base_url = "http://localhost:11434"

    if not model:
        logger.warning(
            "No LLM_MODEL set for provider '%s'; using provider default", provider
        )

    logger.info(
        "LLM provider configured: %s (model: %s)",
        provider,
        model or "(provider default)",
    )

    async def _llm_call(messages: list[dict[str, str]]) -> str:
        return await caller(
            messages,
            api_key=api_key,
            model=model,
            base_url=base_url,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    return _llm_call
