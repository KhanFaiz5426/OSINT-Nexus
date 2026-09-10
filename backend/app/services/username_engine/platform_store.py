"""Platform definition store — loads and validates platform configs."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.services.username_engine.models import PlatformDefinition

logger = logging.getLogger(__name__)

_PLATFORMS_FILE = Path(__file__).parent / "platforms.json"


def load_platforms(
    platforms_file: Path | None = None,
) -> dict[str, PlatformDefinition]:
    """Load platform definitions from the JSON file.

    Returns:
        Dict mapping platform key to PlatformDefinition.
    """
    path = platforms_file or _PLATFORMS_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.error("Platform definitions file not found: %s", path)
        return {}
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in platform definitions: %s", exc)
        return {}

    platforms: dict[str, PlatformDefinition] = {}
    for key, cfg in raw.items():
        try:
            platforms[key] = PlatformDefinition(
                key=key,
                name=cfg["name"],
                url_pattern=cfg["url_pattern"],
                method=cfg.get("method", "GET"),
                success_indicators=cfg.get("success_indicators", {}),
                failure_indicators=cfg.get("failure_indicators", {}),
                rate_limit_rpm=cfg.get("rate_limit_rpm", 30),
                timeout=cfg.get("timeout", 5.0),
                enabled=cfg.get("enabled", True),
                notes=cfg.get("notes", ""),
            )
        except (KeyError, TypeError) as exc:
            logger.warning("Skipping platform '%s': %s", key, exc)

    logger.info("Loaded %d platform definitions", len(platforms))
    return platforms


def get_enabled_platforms(
    platforms: dict[str, PlatformDefinition],
) -> list[PlatformDefinition]:
    """Return only enabled platforms, sorted by name."""
    return sorted(
        (p for p in platforms.values() if p.enabled),
        key=lambda p: p.name,
    )
