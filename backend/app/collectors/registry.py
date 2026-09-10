"""Collector registry — Auto-discover and register all collectors.

The registry maintains a mapping of collector names to collector instances.
Collectors are registered at startup and looked up by name for execution.
"""

from __future__ import annotations

import logging
from typing import Any

from app.collectors.base import OSINTCollector
from app.collectors.cache import CollectorCache
from app.models import TargetType

logger = logging.getLogger(__name__)

# Global registry
_collectors: dict[str, OSINTCollector] = {}


def register_collector(collector: OSINTCollector) -> None:
    """Register a collector instance in the global registry."""
    _collectors[collector.name] = collector
    logger.info("Registered collector: %s v%s", collector.name, collector.version)


def get_collector(name: str) -> OSINTCollector | None:
    """Look up a collector by name."""
    return _collectors.get(name)


def get_all_collectors() -> dict[str, OSINTCollector]:
    """Return all registered collectors."""
    return dict(_collectors)


def get_collectors_for_target(target_type: TargetType) -> list[OSINTCollector]:
    """Return all collectors that support the given target type."""
    return [
        c for c in _collectors.values() if target_type in c.supported_target_types
    ]


def get_collector_names() -> list[str]:
    """Return sorted list of all registered collector names."""
    return sorted(_collectors.keys())


async def initialize_collectors(cache: CollectorCache | None = None) -> None:
    """Initialize and register all built-in collectors.

    Called once at application startup. Creates collector instances
    with optional shared cache. Respects ``collectors.enabled`` from
    the runtime settings store — disabled collectors are skipped.
    """
    from app.collectors.ct_collector import CTCollector
    from app.collectors.dns_collector import DNSCollector
    from app.collectors.github_collector import GitHubCollector
    from app.collectors.gitlab_collector import GitLabCollector
    from app.collectors.hackernews_collector import HackerNewsCollector
    from app.collectors.http_collector import HTTPCollector
    from app.collectors.ip_asn_collector import IPToASNBCollector
    from app.collectors.keybase_collector import KeybaseCollector
    from app.collectors.reddit_collector import RedditCollector
    from app.collectors.search_collector import SearchCollector
    from app.collectors.threat_intel_collector import ThreatIntelCollector
    from app.collectors.whois_collector import WhoisCollector

    collector_classes: list[type[OSINTCollector]] = [
        DNSCollector,
        WhoisCollector,
        CTCollector,
        IPToASNBCollector,
        GitHubCollector,
        HTTPCollector,
        ThreatIntelCollector,
        RedditCollector,
        KeybaseCollector,
        HackerNewsCollector,
        GitLabCollector,
        SearchCollector,
    ]

    # Load enabled/disabled overrides from runtime settings.
    try:
        from app.core.settings_store import get_app_settings
        settings = get_app_settings()
        enabled_map = settings.collectors.enabled
    except Exception:
        enabled_map: dict[str, bool] = {}

    for cls in collector_classes:
        # Peek at the class-level ``name`` without instantiating.
        temp = cls.__new__(cls)
        name = getattr(cls, "name", "")
        if enabled_map.get(name, True) is False:
            logger.info("Collector %s disabled via settings — skipping", name)
            continue
        collector = cls(cache=cache)
        register_collector(collector)

    logger.info("Initialized %d collectors", len(_collectors))


async def get_collector_health() -> list[dict[str, Any]]:
    """Get health check results for all registered collectors."""
    results = []
    for collector in _collectors.values():
        health = await collector.health_check()
        results.append(health)
    return results
