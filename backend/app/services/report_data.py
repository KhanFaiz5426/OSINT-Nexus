"""Report data collector — aggregate investigation data for report generation.

Task 8.1: Collects all entities, relationships, observations, and AI analysis
for a given investigation and assembles them into a single data structure
consumed by the report generator.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.db.client import get_pool
from app.graph.reader import get_investigation_subgraph

logger = logging.getLogger(__name__)


async def collect_report_data(investigation_id: str) -> dict[str, Any]:
    """Aggregate all data needed for an investigation report.

    Pulls investigation metadata, entities, observations, relationships,
    activity log, and AI analysis into a single dict.  All data comes from
    the database — nothing is fabricated.

    Args:
        investigation_id: UUID of the investigation.

    Returns:
        Dict with keys: investigation, entities, observations, relationships,
        activity_log, ai_analysis, graph_summary, generated_at.

    Raises:
        ValueError: If investigation does not exist.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # ── Investigation metadata ───────────────────────────────────────
        inv_row = await conn.fetchrow(
            """
            SELECT id, name, target, target_type, status, depth,
                   api_calls_used, api_budget, created_at, updated_at
            FROM investigations WHERE id = $1
            """,
            investigation_id,
        )
        if inv_row is None:
            raise ValueError(f"Investigation {investigation_id} not found")

        investigation = {
            "id": str(inv_row["id"]),
            "name": inv_row["name"],
            "target": inv_row["target"],
            "target_type": inv_row["target_type"],
            "status": inv_row["status"],
            "depth": inv_row["depth"],
            "api_calls_used": inv_row["api_calls_used"],
            "api_budget": inv_row["api_budget"],
            "created_at": inv_row["created_at"].isoformat(),
            "updated_at": inv_row["updated_at"].isoformat(),
        }

        # ── Entities ─────────────────────────────────────────────────────
        entity_rows = await conn.fetch(
            """
            SELECT id, type, value, confidence, first_seen, last_seen,
                   source_count, properties
            FROM entities
            WHERE investigation_id = $1
            ORDER BY type, value
            """,
            investigation_id,
        )
        entities = []
        for row in entity_rows:
            props = row["properties"]
            if isinstance(props, str):
                try:
                    props = json.loads(props)
                except (json.JSONDecodeError, TypeError):
                    props = {}
            entities.append(
                {
                    "id": row["id"],
                    "type": row["type"],
                    "value": row["value"],
                    "confidence": row["confidence"],
                    "first_seen": row["first_seen"].isoformat() if row["first_seen"] else None,
                    "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
                    "source_count": row["source_count"],
                    "properties": props,
                }
            )

        # ── Observations (evidence) ──────────────────────────────────────
        obs_rows = await conn.fetch(
            """
            SELECT id, source_adapter, source_version, collected_at,
                   method, target, raw_response, normalized_value,
                   confidence, status
            FROM observations
            WHERE investigation_id = $1
            ORDER BY collected_at
            """,
            investigation_id,
        )
        observations = []
        for row in obs_rows:
            raw = row["raw_response"]
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    raw = {}
            observations.append(
                {
                    "id": str(row["id"]),
                    "source_adapter": row["source_adapter"],
                    "source_version": row["source_version"],
                    "collected_at": row["collected_at"].isoformat(),
                    "method": row["method"],
                    "target": row["target"],
                    "raw_response": raw,
                    "normalized_value": row["normalized_value"],
                    "confidence": row["confidence"],
                    "status": row["status"],
                }
            )

        # ── Activity log ─────────────────────────────────────────────────
        activity_rows = await conn.fetch(
            """
            SELECT id, event_type, details, created_at
            FROM activity_log
            WHERE investigation_id = $1
            ORDER BY created_at
            """,
            investigation_id,
        )
        activity_log = []
        for row in activity_rows:
            details = row["details"]
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except (json.JSONDecodeError, TypeError):
                    details = {}
            activity_log.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "details": details,
                    "created_at": row["created_at"].isoformat(),
                }
            )

    # ── Graph relationships ──────────────────────────────────────────────
    try:
        graph = await get_investigation_subgraph(investigation_id)
    except Exception:
        logger.debug("Could not fetch graph for report, using empty")
        graph = {"nodes": [], "edges": []}

    relationships = []
    for edge in graph.get("edges", []):
        data = edge.get("data", {})
        relationships.append(
            {
                "id": data.get("id", ""),
                "source": data.get("source", ""),
                "target": data.get("target", ""),
                "type": data.get("relationship_type", ""),
                "confidence": data.get("confidence", 0.0),
                "evidence": data.get("evidence", []),
                "discovered_at": data.get("discovered_at"),
                "method": data.get("method", ""),
            }
        )

    # ── AI analysis (best-effort, non-blocking) ──────────────────────────
    ai_analysis: dict[str, Any] | None = None
    try:
        from app.ai.analyzer import analyze_investigation
        from app.services.orchestrator import get_graph_summary

        graph_summary = await get_graph_summary(investigation_id)

        pivot_rounds = 0
        pool = await get_pool()
        async with pool.acquire() as conn:
            round_row = await conn.fetchrow(
                """
                SELECT COUNT(*) as cnt FROM activity_log
                WHERE investigation_id = $1
                  AND event_type = 'pivot_round_completed'
                """,
                investigation_id,
            )
            if round_row:
                pivot_rounds = round_row["cnt"]

        from app.ai.client import get_llm_call_fn

        llm_fn = get_llm_call_fn()

        analyzer_output = await analyze_investigation(
            investigation_id=investigation_id,
            target=investigation["target"],
            target_type=investigation["target_type"],
            graph_summary=graph_summary,
            pivot_rounds_completed=pivot_rounds,
            llm_call_fn=llm_fn,
        )
        if analyzer_output:
            ai_analysis = analyzer_output.model_dump()
    except Exception as exc:
        logger.debug("AI analysis not available for report: %s", exc)

    return {
        "investigation": investigation,
        "entities": entities,
        "observations": observations,
        "relationships": relationships,
        "activity_log": activity_log,
        "ai_analysis": ai_analysis,
        "generated_at": datetime.now(UTC).isoformat(),
    }
