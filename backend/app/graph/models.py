"""Neo4j graph models — node/edge shape definitions and schema constraints.

Task 5.1: Define Neo4j node labels and relationship types matching
the entity/relationship models from Phase 4.
"""

from __future__ import annotations

from app.models import EntityType, RelationshipType

# ── Node label definitions ────────────────────────────────────────────────────

# Each EntityType maps to a Neo4j node label.
# Node properties: id, investigation_id, value, confidence, first_seen,
# last_seen, source_count, properties (JSONB-like map).
NODE_LABELS: list[str] = [et.value for et in EntityType]

# ── Relationship type definitions ─────────────────────────────────────────────

# Each RelationshipType maps to a Neo4j relationship type (SCREAMING_SNAKE).
RELATIONSHIP_TYPES: list[str] = [rt.value.upper() for rt in RelationshipType]

# ── Cypher DDL for schema constraints ─────────────────────────────────────────

# Composite unique constraints on (id, investigation_id) for every node label.
# This allows the same entity id across different investigations while keeping
# nodes unique within an investigation.
CONSTRAINTS_CYPHER: list[str] = [
    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE (n.id, n.investigation_id) IS UNIQUE"
    for label in NODE_LABELS
]

# Investigation_id index for filtering subgraphs.
INVESTIGATION_INDEX_CYPHER: list[str] = [
    f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.investigation_id)" for label in NODE_LABELS
]

# ── Node property keys (canonical schema) ─────────────────────────────────────

NODE_PROPERTIES: dict[str, str] = {
    "id": "String — unique identifier ({type}:{value})",
    "investigation_id": "String — owning investigation UUID",
    "value": "String — canonical entity value",
    "confidence": "Float — 0.0–1.0",
    "first_seen": "String (ISO 8601) — earliest observation",
    "last_seen": "String (ISO 8601) — latest observation",
    "source_count": "Integer — number of contributing sources",
    "properties": "Map — additional key-value metadata",
}

# ── Edge property keys ────────────────────────────────────────────────────────

EDGE_PROPERTIES: dict[str, str] = {
    "id": "String — unique relationship key",
    "confidence": "Float — 0.0–1.0",
    "evidence": "List<String> — observation IDs",
    "discovered_at": "String (ISO 8601) — discovery timestamp",
    "method": "String — detection method (e.g. dns_a_record)",
    "investigation_id": "String — owning investigation UUID",
}

# ── Entity type → Neo4j label mapping ─────────────────────────────────────────


def entity_type_to_label(entity_type: EntityType) -> str:
    """Map an EntityType enum to its Neo4j node label."""
    return entity_type.value


def relationship_type_to_cypher(rel_type: RelationshipType) -> str:
    """Map a RelationshipType enum to its Neo4j relationship type string."""
    return rel_type.value.upper()
