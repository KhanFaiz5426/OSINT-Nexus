"""Graph writer — create/update nodes and edges in Neo4j.

Tasks 5.2–5.3:
- 5.2: Create/update nodes from entity list
- 5.3: Create/update edges from relationship list

Uses parameterized Cypher queries to prevent injection. All writes are
scoped to a single investigation_id to enforce data boundaries.
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncDriver

from app.graph.client import get_driver
from app.graph.models import entity_type_to_label, relationship_type_to_cypher
from app.models.processing import ExtractedEntity, ExtractedRelationship

logger = logging.getLogger(__name__)

# ── Cypher templates (parameterized) ──────────────────────────────────────────

# MERGE node by (investigation_id, id) so we upsert within an investigation.
_MERGE_NODE_CYPHER = """
UNWIND $nodes AS node
MERGE (n:{label} {{id: node.id, investigation_id: node.investigation_id}})
SET
    n.value            = node.value,
    n.confidence       = node.confidence,
    n.first_seen       = node.first_seen,
    n.last_seen        = node.last_seen,
    n.source_count     = node.source_count,
    n.properties       = node.properties
"""

# Create edges.  Both source and target must already exist.
_MERGE_EDGE_CYPHER = """
UNWIND $edges AS edge
MATCH (src {{id: edge.source_id, investigation_id: edge.investigation_id}})
MATCH (tgt {{id: edge.target_id, investigation_id: edge.investigation_id}})
MERGE (src)-[r:{rel_type} {{id: edge.id, investigation_id: edge.investigation_id}}]->(tgt)
SET
    r.confidence    = edge.confidence,
    r.evidence      = edge.evidence,
    r.discovered_at = edge.discovered_at,
    r.method        = edge.method
"""


# ── Public API ────────────────────────────────────────────────────────────────


async def write_nodes(
    entities: list[ExtractedEntity],
    *,
    investigation_id: str,
    driver: AsyncDriver | None = None,
) -> int:
    """Write entity nodes to Neo4j (Task 5.2).

    Creates or updates one node per entity, scoped to the investigation.

    Args:
        entities: Resolved entities to write.
        investigation_id: Owning investigation UUID.
        driver: Optional driver override (for testing).

    Returns:
        Number of nodes written.
    """
    _validate_investigation_id(investigation_id)

    if not entities:
        return 0

    driver = driver or await get_driver()

    # Group entities by label for batched writes.
    by_label: dict[str, list[dict[str, Any]]] = {}
    for entity in entities:
        label = entity_type_to_label(entity.entity_type)
        node = _entity_to_node(entity, investigation_id)
        by_label.setdefault(label, []).append(node)

    total = 0
    for label, nodes in by_label.items():
        cypher = _MERGE_NODE_CYPHER.format(label=label)
        async with driver.session() as session:
            result = await session.run(cypher, nodes=nodes)
            summary = await result.consume()
            total += summary.counters.nodes_created or summary.counters.properties_set

    logger.info(
        "Wrote %d nodes for investigation %s", len(entities), investigation_id
    )
    return len(entities)


async def write_edges(
    relationships: list[ExtractedRelationship],
    *,
    investigation_id: str,
    driver: AsyncDriver | None = None,
) -> int:
    """Write relationship edges to Neo4j (Task 5.3).

    Creates or updates one edge per relationship, scoped to the investigation.
    Source and target nodes must already exist.

    Args:
        relationships: Detected relationships to write.
        investigation_id: Owning investigation UUID.
        driver: Optional driver override (for testing).

    Returns:
        Number of edges written.
    """
    _validate_investigation_id(investigation_id)

    if not relationships:
        return 0

    driver = driver or await get_driver()

    # Group by relationship type for batched writes.
    by_type: dict[str, list[dict[str, Any]]] = {}
    for rel in relationships:
        rel_type = relationship_type_to_cypher(rel.rel_type)
        edge = _relationship_to_edge(rel, investigation_id)
        by_type.setdefault(rel_type, []).append(edge)

    total = 0
    for rel_type, edges in by_type.items():
        cypher = _MERGE_EDGE_CYPHER.format(rel_type=rel_type)
        async with driver.session() as session:
            result = await session.run(cypher, edges=edges)
            summary = await result.consume()
            total += summary.counters.relationships_created or summary.counters.properties_set

    logger.info(
        "Wrote %d edges for investigation %s", len(relationships), investigation_id
    )
    return len(relationships)


async def write_graph(
    entities: list[ExtractedEntity],
    relationships: list[ExtractedRelationship],
    *,
    investigation_id: str,
    driver: AsyncDriver | None = None,
) -> tuple[int, int]:
    """Write both nodes and edges to Neo4j in one call.

    Returns:
        (nodes_written, edges_written)
    """
    driver = driver or await get_driver()
    n = await write_nodes(entities, investigation_id=investigation_id, driver=driver)
    e = await write_edges(relationships, investigation_id=investigation_id, driver=driver)
    return n, e


# ── Helpers ───────────────────────────────────────────────────────────────────


def _entity_to_node(
    entity: ExtractedEntity,
    investigation_id: str,
) -> dict[str, Any]:
    """Convert an ExtractedEntity to a Neo4j node property dict."""
    return {
        "id": entity.id,
        "investigation_id": investigation_id,
        "value": entity.value,
        "confidence": entity.confidence,
        "first_seen": entity.first_seen.isoformat() if entity.first_seen else "",
        "last_seen": entity.last_seen.isoformat() if entity.last_seen else "",
        "source_count": len(entity.sources),
        "properties": entity.properties or {},
    }


def _relationship_to_edge(
    rel: ExtractedRelationship,
    investigation_id: str,
) -> dict[str, Any]:
    """Convert an ExtractedRelationship to a Neo4j edge property dict."""
    return {
        "id": rel.id,
        "investigation_id": investigation_id,
        "source_id": rel.source_entity_id,
        "target_id": rel.target_entity_id,
        "confidence": rel.confidence,
        "evidence": rel.evidence_ids or [],
        "discovered_at": rel.discovered_at.isoformat() if rel.discovered_at else "",
        "method": rel.method,
    }


def _validate_investigation_id(investigation_id: str) -> None:
    """Basic validation to prevent empty/None investigation IDs."""
    if not investigation_id or not investigation_id.strip():
        raise ValueError("investigation_id must be a non-empty string")
