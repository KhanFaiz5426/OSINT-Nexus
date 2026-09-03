"""API routes — Entities.

Task 5.9:  GET /entities/{id} — entity details + evidence + neighbors
Task 5.10: GET /entities/{id}/evidence — all observations for entity
"""

import contextlib
import json

from fastapi import APIRouter, HTTPException, Query

from app.db.client import get_pool
from app.graph.reader import get_entity_detail, get_entity_neighbors
from app.models import EntityResponse, RelationshipResponse

router = APIRouter()


@router.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: str,
    investigation_id: str = Query(
        ..., description="Investigation ID that owns this entity"
    ),
) -> EntityResponse:
    """Get entity details including properties and basic metadata.

    The entity must belong to the specified investigation (enforced via
    the investigation_id parameter which is checked against PostgreSQL).
    """
    await _validate_investigation(investigation_id)

    detail = await get_entity_detail(
        entity_id, investigation_id=investigation_id
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    return _detail_to_response(detail, investigation_id)


@router.get("/entities/{entity_id}/evidence", response_model=list[dict])
async def get_entity_evidence(
    entity_id: str,
    investigation_id: str = Query(
        ..., description="Investigation ID that owns this entity"
    ),
) -> list[dict]:
    """Get all observations (evidence) for a specific entity.

    Queries PostgreSQL observations table, filtering by entity value.
    """
    await _validate_investigation(investigation_id)

    # Extract the entity value from the entity_id (e.g., 'domain:example.com' → 'example.com')
    entity_value = _extract_value_from_id(entity_id)

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, source_adapter, source_version, collected_at, method,
                   target, raw_response, normalized_value, confidence, status
            FROM observations
            WHERE investigation_id = $1
              AND (target = $2 OR normalized_value = $2)
            ORDER BY collected_at DESC
            """,
            investigation_id,
            entity_value,
        )

    return [_observation_to_dict(row) for row in rows]


@router.get(
    "/entities/{entity_id}/relationships", response_model=list[RelationshipResponse]
)
async def get_entity_relationships(
    entity_id: str,
    investigation_id: str = Query(
        ..., description="Investigation ID that owns this entity"
    ),
) -> list[RelationshipResponse]:
    """Get all relationships for an entity from the Neo4j graph."""
    await _validate_investigation(investigation_id)

    neighbors = await get_entity_neighbors(
        entity_id,
        investigation_id=investigation_id,
        max_depth=1,
    )

    relationships: list[RelationshipResponse] = []
    for edge in neighbors.get("edges", []):
        data = edge.get("data", edge)
        relationships.append(
            RelationshipResponse(
                id=data.get("id", ""),
                source_entity_id=data.get("source", ""),
                target_entity_id=data.get("target", ""),
                type=data.get("relationship_type", "co_occurs_with"),
                confidence=data.get("confidence", 0.0),
                evidence=data.get("evidence", []),
                discovered_at=data.get("discovered_at"),
                method=data.get("method", ""),
            )
        )

    return relationships


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _validate_investigation(investigation_id: str) -> None:
    """Verify investigation exists in PostgreSQL."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM investigations WHERE id = $1",
            investigation_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found")


def _detail_to_response(
    detail: dict, investigation_id: str
) -> EntityResponse:
    """Convert a Neo4j entity detail dict to an EntityResponse."""
    from app.models import EntityType

    labels = detail.get("labels", [])
    # Map label to EntityType.
    type_str = labels[0] if labels else "Domain"
    try:
        entity_type = EntityType(type_str)
    except ValueError:
        entity_type = EntityType.DOMAIN

    return EntityResponse(
        id=detail.get("id", ""),
        investigation_id=investigation_id,
        type=entity_type,
        value=detail.get("value", ""),
        confidence=detail.get("confidence", 0.0),
        first_seen=_parse_datetime(detail.get("first_seen")),
        last_seen=_parse_datetime(detail.get("last_seen")),
        source_count=detail.get("source_count", 0),
        properties=detail.get("properties", {}),
    )


def _parse_datetime(value: str | None):
    """Parse an ISO 8601 string to datetime, returning None on failure."""
    if not value:
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _extract_value_from_id(entity_id: str) -> str:
    """Extract entity value from a typed ID (e.g., 'domain:example.com' → 'example.com')."""
    if ":" in entity_id:
        return entity_id.split(":", 1)[1]
    return entity_id


def _observation_to_dict(row) -> dict:
    """Convert an asyncpg observation row to a JSON-serializable dict."""
    raw_response = row["raw_response"]
    if isinstance(raw_response, str):
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            raw_response = json.loads(raw_response)

    return {
        "id": str(row["id"]),
        "source_adapter": row["source_adapter"],
        "source_version": row.get("source_version", ""),
        "collected_at": row["collected_at"].isoformat() if row["collected_at"] else "",
        "method": row["method"],
        "target": row["target"],
        "raw_response": raw_response,
        "normalized_value": row.get("normalized_value", ""),
        "confidence": row.get("confidence", 0.0),
        "status": row.get("status", "success"),
    }
