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

def _safe_isoformat(dt: Any) -> str | None:
    if not dt:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


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
            "created_at": _safe_isoformat(inv_row["created_at"]),
            "updated_at": _safe_isoformat(inv_row["updated_at"]),
        }

        # ── Entities ─────────────────────────────────────────────────────
        entity_rows = await conn.fetch(
            """
            SELECT e.id, e.type, e.value, e.confidence, e.first_seen, e.last_seen,
                   e.source_count, e.properties,
                   (
                       SELECT json_group_array(json_object(
                           'observation_id', ep.observation_id,
                           'source_adapter', o.source_adapter,
                           'method', o.method,
                           'target', o.target,
                           'raw_response', o.raw_response
                       ))
                       FROM entity_provenance ep
                       JOIN observations o ON o.id = ep.observation_id
                       WHERE ep.entity_id = e.id
                   ) as provenance_json
            FROM entities e
            WHERE e.investigation_id = $1
            ORDER BY e.type, e.value
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
            
            # Parse provenance and extract real external URLs
            provenance = []
            prov_json = row["provenance_json"]
            if prov_json and prov_json != "[{}]" and prov_json != "[]":
                try:
                    prov_list = json.loads(prov_json)
                    for p in prov_list:
                        # SQLite json_group_array can yield null objects if left join fails,
                        # but we did a correlated subquery so it should be valid unless empty.
                        if not p.get("observation_id"):
                            continue
                        
                        source_url = None
                        raw_resp = p.get("raw_response", "")
                        if isinstance(raw_resp, str) and raw_resp.startswith("{"):
                            try:
                                raw_dict = json.loads(raw_resp)
                                # Try to extract real URL based on known adapters
                                if p["source_adapter"] == "github":
                                    source_url = raw_dict.get("html_url") or raw_dict.get("profile", {}).get("html_url")
                                elif p["source_adapter"] in ("ddg", "search", "http"):
                                    source_url = raw_dict.get("url") or raw_dict.get("link")
                                elif p["source_adapter"] == "hackernews":
                                    source_url = f"https://news.ycombinator.com/user?id={p['target']}"
                                elif p["source_adapter"] == "reddit":
                                    source_url = f"https://reddit.com/user/{p['target']}"
                            except json.JSONDecodeError:
                                pass

                        provenance.append({
                            "observation_id": p["observation_id"],
                            "source_adapter": p["source_adapter"],
                            "method": p["method"],
                            "source_url": source_url
                        })
                except json.JSONDecodeError:
                    pass

            entities.append(
                {
                    "id": row["id"],
                    "type": row["type"],
                    "value": row["value"],
                    "confidence": row["confidence"],
                    "first_seen": _safe_isoformat(row["first_seen"]),
                    "last_seen": _safe_isoformat(row["last_seen"]),
                    "source_count": row["source_count"],
                    "properties": props,
                    "provenance": provenance,
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
                    "collected_at": _safe_isoformat(row["collected_at"]),
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
                    "created_at": _safe_isoformat(row["created_at"]),
                }
            )

        # ── Notes ────────────────────────────────────────────────────────
        notes_rows = await conn.fetch(
            """
            SELECT id, entity_id, content, created_at, updated_at
            FROM notes
            WHERE investigation_id = $1
            ORDER BY created_at
            """,
            investigation_id,
        )
        notes = []
        for row in notes_rows:
            notes.append(
                {
                    "id": row["id"],
                    "entity_id": row["entity_id"],
                    "content": row["content"],
                    "created_at": _safe_isoformat(row["created_at"]),
                    "updated_at": _safe_isoformat(row["updated_at"]),
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

    # ── Collection Scope ─────────────────────────────────────────────────
    sources_used = list(set(obs["source_adapter"] for obs in observations))
    sources_used.sort()

    return {
        "investigation": investigation,
        "entities": entities,
        "observations": observations,
        "relationships": relationships,
        "activity_log": activity_log,
        "notes": notes,
        "sources_used": sources_used,
        "ai_analysis": ai_analysis,
        "generated_at": datetime.now(UTC).isoformat(),
    }


async def collect_workspace_report_data() -> dict[str, Any]:
    """Aggregate all data needed for a workspace-level report.

    Pulls all investigations and top-level metrics into a single dict.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # ── Investigations ───────────────────────────────────────
        inv_rows = await conn.fetch(
            """
            SELECT id, name, target, target_type, status, depth,
                   api_calls_used, api_budget, created_at, updated_at,
                   entity_count, relationship_count, observation_count
            FROM investigations
            ORDER BY created_at DESC
            """
        )
        
        investigations = []
        for row in inv_rows:
            investigations.append({
                "id": str(row["id"]),
                "name": row["name"],
                "target": row["target"],
                "target_type": row["target_type"],
                "status": row["status"],
                "depth": row["depth"],
                "api_calls_used": row["api_calls_used"],
                "api_budget": row["api_budget"],
                "entity_count": row["entity_count"],
                "relationship_count": row["relationship_count"],
                "observation_count": row["observation_count"],
                "created_at": _safe_isoformat(row["created_at"]),
                "updated_at": _safe_isoformat(row["updated_at"]),
            })

        # ── Cross-investigation Metrics ─────────────────────────────────────
        metrics_row = await conn.fetchrow("""
            SELECT 
                (SELECT COUNT(*) FROM investigations) as total_investigations,
                (SELECT COUNT(*) FROM entities) as total_entities,
                (SELECT COUNT(*) FROM relationships) as total_relationships,
                (SELECT COUNT(*) FROM observations) as total_observations
        """)

        # ── Entity Type Distribution ─────────────────────────────────────────
        type_rows = await conn.fetch("""
            SELECT type, COUNT(*) as count 
            FROM entities 
            GROUP BY type 
            ORDER BY count DESC
        """)
        entity_distribution = [{"type": r["type"], "count": r["count"]} for r in type_rows]

        # ── Collection Coverage ──────────────────────────────────────────────
        coverage_rows = await conn.fetch("""
            SELECT source_adapter, COUNT(*) as count 
            FROM observations 
            GROUP BY source_adapter 
            ORDER BY count DESC
        """)
        collection_coverage = [{"source_adapter": r["source_adapter"], "count": r["count"]} for r in coverage_rows]

        # ── Workspace Notes ──────────────────────────────────────────────────
        notes_rows = await conn.fetch("""
            SELECT n.content, n.created_at, i.name as investigation_name
            FROM notes n
            JOIN investigations i ON n.investigation_id = i.id
            ORDER BY n.created_at DESC
        """)
        workspace_notes = [{
            "content": r["content"], 
            "created_at": _safe_isoformat(r["created_at"]), 
            "investigation_name": r["investigation_name"]
        } for r in notes_rows]

        # ── Observed Shared Values ───────────────────────────────────────────
        # Find entities with the exact same type and value across multiple investigations
        shared_rows = await conn.fetch("""
            SELECT type, value, COUNT(DISTINCT investigation_id) as overlap,
                   group_concat(DISTINCT i.name) as shared_across
            FROM entities e
            JOIN investigations i ON e.investigation_id = i.id
            GROUP BY type, value
            HAVING overlap > 1
            ORDER BY overlap DESC, type, value
        """)
        shared_values = [{
            "type": r["type"],
            "value": r["value"],
            "overlap_count": r["overlap"],
            "shared_across": r["shared_across"].split(",") if r["shared_across"] else []
        } for r in shared_rows]

        # ── Activity ─────────────────────────────────────────────────
        activity_rows = await conn.fetch(
            """
            SELECT id, investigation_id, event_type, details, created_at
            FROM activity_log
            ORDER BY created_at DESC
            LIMIT 50
            """
        )
        activity_log = []
        for row in activity_rows:
            details = row["details"]
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except (json.JSONDecodeError, TypeError):
                    details = {}
            activity_log.append({
                "id": row["id"],
                "investigation_id": row["investigation_id"],
                "event_type": row["event_type"],
                "details": details,
                "created_at": _safe_isoformat(row["created_at"]),
            })

    result = {
        "workspace": {
            "name": "Workspace Overview", 
            "total_investigations": metrics_row["total_investigations"],
            "total_entities": metrics_row["total_entities"],
            "total_relationships": metrics_row["total_relationships"],
            "total_observations": metrics_row["total_observations"],
            "entity_distribution": entity_distribution,
            "collection_coverage": collection_coverage,
        },
        "investigations": investigations,
        "shared_values": shared_values,
        "workspace_notes": workspace_notes,
        "activity_log": activity_log,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    
    # Collect full report data for each investigation (outside the connection block)
    full_reports = []
    for inv in investigations:
        full_report = await collect_report_data(inv["id"])
        full_reports.append(full_report)
        
    result["full_reports"] = full_reports
    
    return result
