"""Celery tasks for OSINT collection.

Each collector gets a dedicated Celery task. Tasks handle:
- Cache lookup before collection
- Rate limiting via the collector's built-in limiter
- Raw observation storage to PostgreSQL
- Error logging and status updates
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine in a Celery task (sync context)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="app.tasks.collect_dns", max_retries=2)
def collect_dns_task(
    self,
    investigation_id: str,
    target: str,
    target_type: str,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Collect DNS records for a target."""
    return _run_async(
        _collect_async(
            "dns", investigation_id, target, target_type, force_refresh=force_refresh
        )
    )


@celery_app.task(bind=True, name="app.tasks.collect_whois", max_retries=2)
def collect_whois_task(
    self,
    investigation_id: str,
    target: str,
    target_type: str,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Collect WHOIS data for a target."""
    return _run_async(
        _collect_async(
            "whois", investigation_id, target, target_type, force_refresh=force_refresh
        )
    )


@celery_app.task(bind=True, name="app.tasks.collect_ct", max_retries=2)
def collect_ct_task(
    self,
    investigation_id: str,
    target: str,
    target_type: str,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Collect Certificate Transparency data for a target."""
    return _run_async(
        _collect_async(
            "certificate_transparency",
            investigation_id,
            target,
            target_type,
            force_refresh=force_refresh,
        )
    )


@celery_app.task(bind=True, name="app.tasks.collect_ip_asn", max_retries=2)
def collect_ip_asn_task(
    self,
    investigation_id: str,
    target: str,
    target_type: str,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Collect IP-to-ASN mapping for a target."""
    return _run_async(
        _collect_async(
            "ip_to_asn", investigation_id, target, target_type, force_refresh=force_refresh
        )
    )


@celery_app.task(bind=True, name="app.tasks.collect_github", max_retries=2)
def collect_github_task(
    self,
    investigation_id: str,
    target: str,
    target_type: str,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Collect GitHub profile and repository data for a username."""
    return _run_async(
        _collect_async(
            "github", investigation_id, target, target_type, force_refresh=force_refresh
        )
    )


@celery_app.task(bind=True, name="app.tasks.collect_http", max_retries=2)
def collect_http_task(
    self,
    investigation_id: str,
    target: str,
    target_type: str,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Collect HTTP metadata and technology data for a target."""
    return _run_async(
        _collect_async(
            "http", investigation_id, target, target_type, force_refresh=force_refresh
        )
    )


@celery_app.task(bind=True, name="app.tasks.collect_threat_intel", max_retries=2)
def collect_threat_intel_task(
    self,
    investigation_id: str,
    target: str,
    target_type: str,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Collect threat intelligence data for a target."""
    return _run_async(
        _collect_async(
            "threat_intel",
            investigation_id,
            target,
            target_type,
            force_refresh=force_refresh,
        )
    )


@celery_app.task(bind=True, name="app.tasks.collect_search", max_retries=2)
def collect_search_task(
    self,
    investigation_id: str,
    target: str,
    target_type: str,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Collect public web search results for a target."""
    return _run_async(
        _collect_async(
            "search",
            investigation_id,
            target,
            target_type,
            force_refresh=force_refresh,
        )
    )


async def _collect_async(
    collector_name: str,
    investigation_id: str,
    target: str,
    target_type: str,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Internal async collection logic shared by all Celery tasks."""
    from app.collectors.cache import CollectorCache

    # Initialize collectors if needed
    from app.collectors.registry import get_all_collectors, get_collector, initialize_collectors
    from app.core.redis import get_redis
    from app.db.client import get_pool
    from app.models import TargetType
    if not get_all_collectors():
        try:
            redis_client = await get_redis()
            cache = CollectorCache(redis_client)
            await initialize_collectors(cache=cache)
        except Exception:
            await initialize_collectors(cache=None)

    collector = get_collector(collector_name)
    if collector is None:
        return {"error": f"Unknown collector: {collector_name}"}

    # Execute collection
    tt = TargetType(target_type)
    result = await collector.collect(target, target_type=tt, force_refresh=force_refresh)

    # Store raw observation in PostgreSQL
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO observations
                    (investigation_id, source_adapter, source_version, collected_at,
                     method, target, raw_response, normalized_value, confidence, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                investigation_id,
                result.collector_name,
                result.collector_version,
                result.collected_at,
                result.query,
                result.target,
                json.dumps(result.raw_response),
                result.normalized_value,
                result.confidence,
                result.status.value,
            )
    except Exception as exc:
        logger.error("Failed to store observation for %s/%s: %s", collector_name, target, exc)

    return {
        "collector": result.collector_name,
        "target": result.target,
        "status": result.status.value,
        "confidence": result.confidence,
        "error_message": result.error_message,
    }
