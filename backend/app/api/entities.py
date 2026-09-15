"""API routes — Entities.

Task 5.9:  GET /entities/{id} — entity details + evidence + neighbors
Task 5.10: GET /entities/{id}/evidence — all observations for entity
"""

import contextlib
import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.client import get_pool
from app.graph.reader import get_entity_detail, get_entity_neighbors
from app.models import (
    EntityCreate,
    EntityResponse,
    RelationshipCreate,
    RelationshipResponse,
    SourceAvailabilityResponse,
    SourceAvailabilityStatus,
)

router = APIRouter()


@router.get("/entities/{entity_id:path}/evidence", response_model=list[dict])
async def get_entity_evidence(
    entity_id: str,
    investigation_id: str = Query(..., description="Investigation ID that owns this entity"),
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
              AND (target = $2 OR normalized_value ILIKE $2)
            ORDER BY collected_at DESC
            """,
            investigation_id,
            entity_value,
        )

    return [_observation_to_dict(row) for row in rows]


@router.get("/entities/{entity_id:path}/relationships", response_model=list[RelationshipResponse])
async def get_entity_relationships(
    entity_id: str,
    investigation_id: str = Query(..., description="Investigation ID that owns this entity"),
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
        rel_type = (data.get("relationship_type", "co_occurs_with") or "co_occurs_with").lower()
        relationships.append(
            RelationshipResponse(
                id=data.get("id", ""),
                source_entity_id=data.get("source", ""),
                target_entity_id=data.get("target", ""),
                type=rel_type,
                confidence=data.get("confidence", 0.0),
                evidence=data.get("evidence", []),
                discovered_at=data.get("discovered_at"),
                method=data.get("method", ""),
            )
        )

    return relationships


@router.get("/entities/{entity_id:path}/provenance", response_model=list[dict])
async def get_entity_provenance(
    entity_id: str,
    investigation_id: str = Query(..., description="Investigation ID that owns this entity"),
) -> list[dict]:
    """Get the provenance trail for an entity.

    Returns the list of observations that discovered or contributed to
    this entity, showing the evidence chain.
    """
    await _validate_investigation(investigation_id)

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ep.observation_id, ep.created_at,
                   o.source_adapter, o.collected_at, o.method, o.target,
                   o.confidence, o.status
            FROM entity_provenance ep
            LEFT JOIN observations o ON ep.observation_id = o.id
            WHERE ep.entity_id = $1 AND ep.investigation_id = $2
            ORDER BY ep.created_at
            """,
            entity_id,
            investigation_id,
        )

    return [
        {
            "observation_id": str(row["observation_id"]),
            "source_adapter": row["source_adapter"],
            "collected_at": row["collected_at"].isoformat() if row["collected_at"] else "",
            "method": row["method"],
            "target": row["target"],
            "confidence": row["confidence"],
            "status": row["status"],
            "discovered_at": row["created_at"].isoformat() if row["created_at"] else "",
        }
        for row in rows
    ]


class ConfidenceOverrideRequest(BaseModel):
    """Request model for overriding entity confidence."""

    confidence: float = Field(..., ge=0.0, le=1.0, description="New confidence score")
    reason: str = Field(default="", description="Reason for the override")


@router.post("/entities", response_model=EntityResponse, status_code=201)
async def create_entity(
    body: EntityCreate,
    investigation_id: str = Query(..., description="Investigation ID to add this entity to"),
) -> EntityResponse:
    """Create a manual entity in the investigation.

    Adds an entity to both PostgreSQL and Neo4j. The entity ID is
    auto-generated from the type and value (e.g., 'domain:example.com').
    """
    await _validate_investigation(investigation_id)

    # Build entity ID from type and value
    entity_id = f"{body.entity_type.value.lower()}:{body.value}"
    now = datetime.now(UTC)

    # Write to PostgreSQL
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO entities (id, investigation_id, type, value, confidence,
                                  first_seen, last_seen, source_count, properties, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (id) DO UPDATE SET
                confidence = EXCLUDED.confidence,
                properties = EXCLUDED.properties,
                last_seen = EXCLUDED.last_seen
            """,
            entity_id,
            investigation_id,
            body.entity_type.value,
            body.value,
            body.confidence,
            now,
            now,
            1,
            json.dumps(body.properties),
            now,
        )

    # Write to Neo4j
    try:
        from app.graph.writer import write_nodes
        from app.models.processing import ExtractedEntity

        entity = ExtractedEntity(
            id=entity_id,
            entity_type=body.entity_type,
            value=body.value,
            confidence=body.confidence,
            first_seen=now,
            last_seen=now,
            sources=["manual"],
            properties=body.properties,
        )
        await write_nodes([entity], investigation_id=investigation_id)
    except Exception:
        pass  # Best effort for graph write

    return EntityResponse(
        id=entity_id,
        investigation_id=investigation_id,
        type=body.entity_type,
        value=body.value,
        confidence=body.confidence,
        first_seen=now,
        last_seen=now,
        source_count=1,
        properties=body.properties,
    )


@router.patch("/entities/{entity_id:path}/confidence")
async def override_confidence(
    entity_id: str,
    body: ConfidenceOverrideRequest,
    investigation_id: str = Query(..., description="Investigation ID that owns this entity"),
) -> dict:
    """Override the confidence score for an entity.

    Stores the override in PostgreSQL and updates the entity's confidence.
    """
    await _validate_investigation(investigation_id)

    # Get current confidence
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT confidence FROM entities WHERE id = $1 AND investigation_id = $2",
            entity_id,
            investigation_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    original_confidence = row["confidence"]

    # Apply override
    from app.services.confidence import apply_manual_override

    result = apply_manual_override(
        entity_id=entity_id,
        investigation_id=investigation_id,
        override_confidence=body.confidence,
        original_confidence=original_confidence,
        reason=body.reason,
    )

    return result


@router.post(
    "/entities/relationships",
    response_model=RelationshipResponse,
    status_code=201,
)
async def create_relationship(
    body: RelationshipCreate,
    investigation_id: str = Query(..., description="Investigation ID to add this relationship to"),
) -> RelationshipResponse:
    """Create a manual relationship between two entities.

    Adds a relationship to the Neo4j graph. Both source and target
    entities must already exist.
    """
    await _validate_investigation(investigation_id)

    from uuid import uuid4

    from app.graph.models import relationship_type_to_cypher

    rel_id = str(uuid4())
    now = datetime.now(UTC)

    # Write to Neo4j
    rel_type_cypher = relationship_type_to_cypher(body.rel_type)

    async with driver.session() as session:
        query = f"""
        MATCH (src {{id: $source_id, investigation_id: $investigation_id}})
        MATCH (tgt {{id: $target_id, investigation_id: $investigation_id}})
        CREATE (src)-[r:{rel_type_cypher} {{
            id: $rel_id,
            investigation_id: $investigation_id,
            confidence: $confidence,
            evidence: [],
            discovered_at: $discovered_at,
            method: $method
        }}]->(tgt)
        RETURN r.id AS rel_id
        """
        result = await session.run(
            query,
            source_id=body.source_entity_id,
            target_id=body.target_entity_id,
            investigation_id=investigation_id,
            rel_id=rel_id,
            confidence=body.confidence,
            discovered_at=now.isoformat(),
            method=body.method,
        )
        await result.single()

    return RelationshipResponse(
        id=rel_id,
        source_entity_id=body.source_entity_id,
        target_entity_id=body.target_entity_id,
        type=body.rel_type,
        confidence=body.confidence,
        evidence=[],
        discovered_at=now,
        method=body.method,
    )


@router.get(
    "/entities/{entity_id}/source-availability",
    response_model=SourceAvailabilityResponse,
)
async def get_source_availability(
    entity_id: str,
    investigation_id: str = Query(..., description="Investigation ID that owns this entity"),
) -> SourceAvailabilityResponse:
    """Check source URL availability for an entity.

    Uses evidence-based URL resolution: looks up the entity's profile_url
    property or constructs a URL from the entity type and sources. Then
    performs a HEAD request to verify accessibility. Results are cached
    for 1 hour.
    """
    await _validate_investigation(investigation_id)

    # Get entity details to find the source URL
    detail = await get_entity_detail(entity_id, investigation_id=investigation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    properties = detail.get("properties", {})
    entity_value = detail.get("value", "")
    labels = detail.get("labels", [])
    entity_type = labels[0] if labels else ""

    # Resolve source URL from evidence/properties (never construct from name alone)
    source_url = _resolve_source_url(entity_type, entity_value, properties)
    if not source_url:
        raise HTTPException(
            status_code=404,
            detail="No source URL available for this entity",
        )

    # Check availability
    from app.services.source_availability import check_source_availability

    result = await check_source_availability(source_url)

    return SourceAvailabilityResponse(
        url=result["url"],
        status=SourceAvailabilityStatus(result["status"]),
        checked_at=result["checked_at"],
        detail=result["detail"],
        final_url=result.get("final_url", result["url"]),
    )


@router.get("/entities/{entity_id:path}", response_model=EntityResponse)
async def get_entity(
    entity_id: str,
    investigation_id: str = Query(..., description="Investigation ID that owns this entity"),
) -> EntityResponse:
    """Get entity details including properties and basic metadata.

    The entity must belong to the specified investigation (enforced via
    the investigation_id parameter which is checked against PostgreSQL).
    """
    await _validate_investigation(investigation_id)

    detail = await get_entity_detail(entity_id, investigation_id=investigation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    return _detail_to_response(detail, investigation_id)


def _resolve_source_url(entity_type: str, value: str, properties: dict) -> str | None:
    """Resolve the source URL for an entity from evidence/properties.

    Prefers properties.profile_url (set during extraction from real API responses).
    Falls back to properties.url. Never constructs URLs from entity names.
    """
    profile_url = properties.get("profile_url", "")
    if isinstance(profile_url, str) and profile_url.startswith("http"):
        return profile_url

    url = properties.get("url", "")
    if isinstance(url, str) and url.startswith("http"):
        return url

    return None


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


def _detail_to_response(detail: dict, investigation_id: str) -> EntityResponse:
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
