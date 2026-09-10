"""API routes — Entity-level AI Analysis.

Provides an endpoint for AI-powered entity intelligence. Uses the existing
LLM client infrastructure to analyze a single entity in the context of its
investigation. All data comes from stored evidence — nothing is fabricated.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.security import sanitize_error_message
from app.db.client import get_pool

logger = logging.getLogger(__name__)

router = APIRouter()


async def _collect_entity_context(
    entity_id: str,
    investigation_id: str,
) -> dict[str, Any]:
    """Gather all context needed for entity AI analysis.

    Pulls entity details, evidence, relationships, and investigation metadata.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Investigation metadata
        inv_row = await conn.fetchrow(
            """
            SELECT id, name, target, target_type, status, depth,
                   created_at, updated_at
            FROM investigations WHERE id = $1
            """,
            investigation_id,
        )
        if inv_row is None:
            raise ValueError("Investigation not found")

        # Entity details
        ent_row = await conn.fetchrow(
            """
            SELECT id, type, value, confidence, first_seen, last_seen,
                   source_count, properties
            FROM entities
            WHERE id = $1 AND investigation_id = $2
            """,
            entity_id,
            investigation_id,
        )
        # Fallback: entity may belong to a different investigation due to
        # the global unique constraint on entity id.
        if ent_row is None:
            ent_row = await conn.fetchrow(
                """
                SELECT id, type, value, confidence, first_seen, last_seen,
                       source_count, properties
                FROM entities
                WHERE id = $1
                """,
                entity_id,
            )
        if ent_row is None:
            raise ValueError("Entity not found")

        # Entity evidence (observations)
        evidence_rows = await conn.fetch(
            """
            SELECT DISTINCT o.id, o.source_adapter, o.collected_at,
                   o.method, o.target, o.normalized_value,
                   o.confidence, o.status
            FROM entity_provenance ep
            JOIN observations o ON o.id = ep.observation_id
            WHERE ep.entity_id = $1 AND ep.investigation_id = $2
            ORDER BY o.collected_at DESC
            LIMIT 20
            """,
            entity_id,
            investigation_id,
        )
        # Fallback: provenance may be recorded under a different investigation
        if not evidence_rows:
            evidence_rows = await conn.fetch(
                """
                SELECT DISTINCT o.id, o.source_adapter, o.collected_at,
                       o.method, o.target, o.normalized_value,
                       o.confidence, o.status
                FROM entity_provenance ep
                JOIN observations o ON o.id = ep.observation_id
                WHERE ep.entity_id = $1
                ORDER BY o.collected_at DESC
                LIMIT 20
                """,
                entity_id,
            )

        # Fallback: value-based matching if no provenance
        if not evidence_rows:
            entity_value = entity_id.split(":", 1)[1] if ":" in entity_id else entity_id
            evidence_rows = await conn.fetch(
                """
                SELECT id, source_adapter, collected_at, method,
                       target, normalized_value, confidence, status
                FROM observations
                WHERE investigation_id = $1
                  AND (target = $2 OR normalized_value = $2)
                ORDER BY collected_at DESC
                LIMIT 20
                """,
                investigation_id,
                entity_value,
            )

    # Entity relationships from Neo4j
    relationships = []
    try:
        from app.graph.reader import get_entity_neighbors

        neighbors = await get_entity_neighbors(
            entity_id, investigation_id=investigation_id, max_depth=1,
        )
        for edge in neighbors.get("edges", []):
            data = edge.get("data", edge)
            relationships.append({
                "source": data.get("source", ""),
                "target": data.get("target", ""),
                "type": data.get("relationship_type", ""),
                "confidence": data.get("confidence", 0.0),
                "method": data.get("method", ""),
            })

        # Gather related entity labels
        for node in neighbors.get("nodes", []):
            nd = node.get("data", node)
            if nd.get("id") != entity_id:
                relationships.append({
                    "_node": True,
                    "id": nd.get("id", ""),
                    "type": nd.get("type", ""),
                    "label": nd.get("label", nd.get("value", "")),
                    "confidence": nd.get("confidence", 0),
                })
    except Exception as exc:
        logger.debug("Could not fetch entity neighbors: %s", exc)

    # Parse entity properties
    props = ent_row["properties"]
    if isinstance(props, str):
        try:
            props = json.loads(props)
        except (json.JSONDecodeError, TypeError):
            props = {}

    return {
        "investigation": {
            "id": str(inv_row["id"]),
            "name": inv_row["name"],
            "target": inv_row["target"],
            "target_type": inv_row["target_type"],
            "status": inv_row["status"],
        },
        "entity": {
            "id": ent_row["id"],
            "type": ent_row["type"],
            "value": ent_row["value"],
            "confidence": ent_row["confidence"],
            "first_seen": ent_row["first_seen"].isoformat() if ent_row["first_seen"] else None,
            "last_seen": ent_row["last_seen"].isoformat() if ent_row["last_seen"] else None,
            "source_count": ent_row["source_count"],
            "properties": props or {},
        },
        "evidence": [
            {
                "source": row["source_adapter"],
                "method": row["method"],
                "target": row["target"],
                "confidence": row.get("confidence", 0.0),
                "collected_at": row["collected_at"].isoformat() if row["collected_at"] else "",
                "status": row.get("status", "success"),
            }
            for row in evidence_rows
        ],
        "relationships": [r for r in relationships if not r.get("_node")],
        "related_entities": [
            {"id": r["id"], "type": r["type"], "label": r["label"], "confidence": r["confidence"]}
            for r in relationships if r.get("_node")
        ],
    }


def _build_entity_analysis_prompt(ctx: dict[str, Any]) -> list[dict[str, str]]:
    """Build the LLM prompt for entity-level AI analysis."""
    inv = ctx["investigation"]
    ent = ctx["entity"]
    evidence = ctx["evidence"]
    rels = ctx["relationships"]
    related = ctx["related_entities"]

    system_msg = (
        "You are an OSINT analysis assistant. Given details about a specific entity "
        "within an investigation, provide a focused analysis.\n\n"
        "You MUST respond with valid JSON matching this schema:\n"
        "{\n"
        '  "what_is": "<string: 1-2 sentence explanation of what this entity is>",\n'
        '  "key_information": ["<list of key facts discovered about this entity>"],\n'
        '  "evidence_summary": "<string: summary of the evidence supporting this entity>",\n'
        '  "confidence_assessment": "<string: why confidence is at this level>",\n'
        '  "connection_to_target": "<string: how this entity connects to the investigation target>",\n'
        '  "significance": "<string: why this entity may matter to the investigation>",\n'
        '  "uncertainties": ["<list of uncertainties, gaps, or conflicting evidence>"],\n'
        '  "ai_inferences": ["<list of inferences NOT directly from evidence>"]\n'
        "}\n\n"
        "CRITICAL RULES:\n"
        "- Base your analysis ONLY on the provided evidence. Do NOT fabricate information.\n"
        "- Clearly distinguish confirmed evidence from inference.\n"
        "- If evidence is sparse, say so honestly.\n"
        "- Keep key_information factual and sourced from observations.\n"
        "- ai_inferences should be clearly labeled as analytical conclusions, not facts.\n"
        "- Be concise but thorough."
    )

    user_parts = [
        f"Investigation: {inv['name']}",
        f"Investigation target: {inv['target']} (type: {inv['target_type']})",
        f"\n--- Entity Under Analysis ---",
        f"Entity ID: {ent['id']}",
        f"Type: {ent['type']}",
        f"Value: {ent['value']}",
        f"Confidence: {ent['confidence']:.2f}",
        f"Sources: {ent['source_count']}",
    ]

    if ent.get("first_seen"):
        user_parts.append(f"First seen: {ent['first_seen']}")
    if ent.get("last_seen"):
        user_parts.append(f"Last seen: {ent['last_seen']}")

    # Properties
    props = ent.get("properties", {})
    if props:
        filtered = {k: v for k, v in props.items() if not k.startswith("_") and k != "sources"}
        if filtered:
            user_parts.append(f"\nProperties: {json.dumps(filtered, default=str)[:500]}")

    # Evidence
    if evidence:
        user_parts.append(f"\n--- Evidence ({len(evidence)} observations) ---")
        for ev in evidence[:15]:
            user_parts.append(
                f"  - [{ev['source']}] {ev['method']} → {ev['target']} "
                f"(conf: {ev['confidence']:.2f}, status: {ev['status']})"
            )
    else:
        user_parts.append("\n--- No direct evidence observations ---")

    # Relationships
    if rels:
        user_parts.append(f"\n--- Relationships ({len(rels)}) ---")
        for rel in rels[:15]:
            user_parts.append(
                f"  - {rel['source']} --[{rel['type']}]--> {rel['target']} "
                f"(conf: {rel['confidence']:.2f})"
            )

    # Related entities
    if related:
        user_parts.append(f"\n--- Related Entities ({len(related)}) ---")
        for re_ent in related[:10]:
            user_parts.append(
                f"  - {re_ent['type']}:{re_ent['label']} (conf: {re_ent['confidence']:.2f})"
            )

    user_parts.append(
        "\nProvide your analysis of this entity. Focus on how it relates "
        "to the investigation target and what the evidence tells us."
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


@router.get("/entities/{entity_id:path}/ai-analysis")
async def get_entity_ai_analysis(
    entity_id: str,
    investigation_id: str = Query(
        ..., description="Investigation ID that owns this entity"
    ),
) -> dict[str, Any]:
    """Get AI-powered analysis for a specific entity.

    Uses the existing LLM client infrastructure to analyze entity context.
    Clearly separates confirmed evidence from AI inferences.
    """
    # Collect entity context
    try:
        ctx = await _collect_entity_context(entity_id, investigation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None

    ent = ctx["entity"]
    inv = ctx["investigation"]
    evidence = ctx["evidence"]
    related = ctx["related_entities"]
    rels = ctx["relationships"]

    # Build confirmed facts from evidence
    confirmed_facts = []
    for ev in evidence:
        confirmed_facts.append({
            "fact": f"Observed via {ev['source']} ({ev['method']}) targeting {ev['target']}",
            "source": ev["source"],
            "confidence": ev["confidence"],
            "collected_at": ev["collected_at"],
        })

    # Call LLM for AI analysis
    ai_analysis: dict[str, Any] | None = None
    try:
        from app.ai.client import get_llm_call_fn
        from app.ai.response_parser import extract_json_from_llm_response

        llm_fn = get_llm_call_fn()
        if llm_fn is not None:
            messages = _build_entity_analysis_prompt(ctx)
            response_text = await llm_fn(messages)
            ai_analysis = extract_json_from_llm_response(response_text)
    except Exception as exc:
        logger.warning("Entity AI analysis failed: %s: %s", type(exc).__name__, str(exc)[:300])

    # Build response
    return {
        "entity_id": ent["id"],
        "entity_type": ent["type"],
        "entity_value": ent["value"],
        "entity_confidence": ent["confidence"],
        "investigation_target": inv["target"],
        "investigation_target_type": inv["target_type"],
        "analysis": ai_analysis or {
            "what_is": f"A {ent['type']} entity with value '{ent['value']}' discovered during the investigation.",
            "key_information": [
                f"Discovered from {ent['source_count']} source(s)",
                f"Confidence level: {ent['confidence'] * 100:.0f}%",
            ],
            "evidence_summary": (
                f"{len(evidence)} observation(s) support this entity."
                if evidence else
                "No direct evidence observations recorded for this entity."
            ),
            "confidence_assessment": (
                f"Confidence is {ent['confidence'] * 100:.0f}% based on "
                f"{ent['source_count']} source(s)."
            ),
            "connection_to_target": (
                f"Connected to investigation target '{inv['target']}' through "
                f"{len(rels)} relationship(s)."
                if rels else
                f"No direct connections to investigation target '{inv['target']}' found."
            ),
            "significance": "AI analysis not available. Manual review recommended.",
            "uncertainties": [
                "AI analysis was not performed — these are deterministic observations only."
            ],
            "ai_inferences": [],
        },
        "confirmed_facts": confirmed_facts,
        "evidence_count": len(evidence),
        "relationship_count": len(rels),
        "related_entities": [
            {"id": r["id"], "type": r["type"], "label": r["label"]}
            for r in related[:10]
        ],
        "generated_at": datetime.now(UTC).isoformat(),
    }
