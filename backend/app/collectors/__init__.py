"""Collectors package — OSINT source adapters.

This package contains:
- base.py: OSINTCollector abstract base class
- cache.py: In-memory TTLCache response caching
- rate_limiter.py: Token bucket rate limiting
- retry.py: Exponential backoff retry logic
- registry.py: Collector registration and discovery
- *_collector.py: Individual collector implementations
"""

from app.collectors.base import OSINTCollector
from app.collectors.cache import CollectorCache
from app.collectors.rate_limiter import TokenBucketRateLimiter
from app.collectors.registry import (
    get_all_collectors,
    get_collector,
    get_collector_health,
    get_collector_names,
    get_collectors_for_target,
    initialize_collectors,
    register_collector,
)

__all__ = [
    "OSINTCollector",
    "CollectorCache",
    "TokenBucketRateLimiter",
    "get_all_collectors",
    "get_collector",
    "get_collector_names",
    "get_collectors_for_target",
    "get_collector_health",
    "initialize_collectors",
    "register_collector",
]
