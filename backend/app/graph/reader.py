"""Graph reader — query Neo4j for investigation subgraphs, neighbors, paths.

Tasks 5.4–5.6:
- 5.4: Query subgraph for an investigation (all entities + relationships)
- 5.5: Query neighbors of a specific entity
- 5.6: Query multi-hop paths between entities

All queries are parameterized to prevent injection. Queries are scoped
by investigation_id to enforce data boundaries.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from neo4j import AsyncDriver

from app.graph.client import get_driver

logger = logging.getLogger(__name__)


# ── Investigation subgraph (Task 5.4) ─────────────────────────────────────────


async def get_investigation_subgraph(
    investigation_id: str,
    *,
    driver: AsyncDriver | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return the full knowledge graph for an investigation (Task 5.4).

    Returns all nodes and edges scoped to the investigation, formatted
    for Cytoscape.js consumption.

    Args:
        investigation_id: The investigation UUID.
        driver: Optional driver override.

    Returns:
        {"nodes": [...], "edges": [...]} where each entry is a dict
        compatible with Cytoscape.js element format.
    """
    _validate_id(investigation_id)
    driver = driver or await get_driver()

    nodes_query = """
    MATCH (n)
    WHERE n.investigation_id = $investigation_id
    RETURN
        n.id                AS node_id,
        labels(n)           AS labels,
        n.value             AS value,
        n.confidence        AS confidence,
        n.first_seen        AS first_seen,
        n.last_seen         AS last_seen,
        n.source_count      AS source_count,
        n.properties        AS properties
    """
    edges_query = """
    MATCH (src)-[r]->(tgt)
    WHERE src.investigation_id = $investigation_id
      AND tgt.investigation_id = $investigation_id
      AND r.investigation_id   = $investigation_id
    RETURN
        r.id                AS edge_id,
        src.id              AS source,
        tgt.id              AS target,
        type(r)             AS relationship_type,
        r.confidence        AS confidence,
        r.evidence          AS evidence,
        r.discovered_at     AS discovered_at,
        r.method            AS method
    """
    params = {"investigation_id": investigation_id}

    async with driver.session() as session:
        nodes_result = await session.run(nodes_query, params)
        nodes = [dict(record) async for record in nodes_result]

        edges_result = await session.run(edges_query, params)
        edges = [dict(record) async for record in edges_result]

    # Convert to Cytoscape.js format
    cyto_nodes = [_node_to_cytoscape(n) for n in nodes]
    cyto_edges = [_edge_to_cytoscape(e) for e in edges]

    logger.info(
        "Retrieved subgraph for %s: %d nodes, %d edges",
        investigation_id,
        len(cyto_nodes),
        len(cyto_edges),
    )
    return {"nodes": cyto_nodes, "edges": cyto_edges}


# ── Entity neighbors (Task 5.5) ──────────────────────────────────────────────


async def get_entity_neighbors(
    entity_id: str,
    *,
    investigation_id: str,
    max_depth: int = 1,
    driver: AsyncDriver | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return the neighbors of a specific entity (Task 5.5).

    Traverses up to `max_depth` hops from the entity, scoped to the
    investigation.

    Args:
        entity_id: The entity ID (e.g., 'domain:example.com').
        investigation_id: Owning investigation UUID.
        max_depth: Maximum traversal depth (default 1 = direct neighbors).
        driver: Optional driver override.

    Returns:
        {"nodes": [...], "edges": [...]} in Cytoscape.js format.
    """
    _validate_id(entity_id)
    _validate_id(investigation_id)
    driver = driver or await get_driver()

    # Clamp depth to prevent unbounded traversal.
    max_depth = max(1, min(max_depth, 6))

    # Use f-string for depth parameter (Cypher range syntax requires literal int).
    # Match variable-length paths, collect all node IDs on valid paths, then
    # find edges between those nodes.
    edges_query = f"""
    MATCH path = (center)-[*1..{max_depth}]-(neighbor)
    WHERE center.id = $entity_id
      AND center.investigation_id = $investigation_id
      AND ALL(n IN nodes(path) WHERE n.investigation_id = $investigation_id)
    WITH [n IN nodes(path) | n.id] AS node_ids
    MATCH (src)-[r]->(tgt)
    WHERE src.id IN node_ids
      AND tgt.id IN node_ids
      AND src.investigation_id = $investigation_id
      AND tgt.investigation_id = $investigation_id
      AND r.investigation_id = $investigation_id
    RETURN DISTINCT
        r.id                AS edge_id,
        src.id              AS source,
        tgt.id              AS target,
        type(r)             AS relationship_type,
        r.confidence        AS confidence,
        r.evidence          AS evidence,
        r.discovered_at     AS discovered_at,
        r.method            AS method
    """

    # Get nodes separately.
    nodes_query = """
    MATCH (n)
    WHERE n.investigation_id = $investigation_id
      AND (n.id = $entity_id
           OR n.id IN $neighbor_ids)
    RETURN
        n.id            AS node_id,
        labels(n)       AS labels,
        n.value         AS value,
        n.confidence    AS confidence,
        n.first_seen    AS first_seen,
        n.last_seen     AS last_seen,
        n.source_count  AS source_count,
        n.properties    AS properties
    """

    async with driver.session() as session:
        # First get the edges and neighbor IDs.
        result = await session.run(
            edges_query, entity_id=entity_id, investigation_id=investigation_id
        )
        raw_edges = [dict(record) async for record in result]

        # Collect neighbor IDs from edges.
        neighbor_ids: set[str] = set()
        neighbor_ids.add(entity_id)
        for edge in raw_edges:
            neighbor_ids.add(edge["source"])
            neighbor_ids.add(edge["target"])

        # Now fetch node details.
        nodes_result = await session.run(
            nodes_query,
            entity_id=entity_id,
            investigation_id=investigation_id,
            neighbor_ids=list(neighbor_ids),
        )
        nodes = [dict(record) async for record in nodes_result]

    cyto_nodes = [_node_to_cytoscape(n) for n in nodes]
    cyto_edges = [_edge_to_cytoscape(e) for e in raw_edges]

    return {"nodes": cyto_nodes, "edges": cyto_edges}


# ── Multi-hop paths (Task 5.6) ───────────────────────────────────────────────


async def get_multi_hop_paths(
    source_id: str,
    target_id: str,
    *,
    investigation_id: str,
    max_hops: int = 4,
    driver: AsyncDriver | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Find multi-hop paths between two entities (Task 5.6).

    Uses bounded BFS to discover connections between entities.

    Args:
        source_id: Starting entity ID.
        target_id: Ending entity ID.
        investigation_id: Owning investigation UUID.
        max_hops: Maximum path length (default 4).
        driver: Optional driver override.

    Returns:
        {"nodes": [...], "edges": [...]} in Cytoscape.js format.
    """
    _validate_id(source_id)
    _validate_id(target_id)
    _validate_id(investigation_id)
    driver = driver or await get_driver()

    max_hops = max(1, min(max_hops, 10))

    # Use f-string for Cypher range syntax (requires literal int).
    all_paths_query = f"""
    MATCH path = (src)-[*1..{max_hops}]-(tgt)
    WHERE src.id = $source_id
      AND tgt.id = $target_id
      AND src.investigation_id = $investigation_id
      AND tgt.investigation_id = $investigation_id
      AND ALL(n IN nodes(path) WHERE n.investigation_id = $investigation_id)
      AND ALL(r IN relationships(path) WHERE r.investigation_id = $investigation_id)
    WITH path
    LIMIT 10
    RETURN
        [n IN nodes(path) | n]         AS path_nodes,
        [r IN relationships(path) | r] AS path_rels
    """

    async with driver.session() as session:
        result = await session.run(
            all_paths_query,
            source_id=source_id,
            target_id=target_id,
            investigation_id=investigation_id,
        )
        records = [dict(record) async for record in result]

    # Collect all unique nodes and edges across paths.
    all_nodes: dict[str, dict[str, Any]] = {}
    all_edges: list[dict[str, Any]] = []

    for record in records:
        for node in record["path_nodes"]:
            node_dict = dict(node)
            nid = node_dict.get("node_id", node_dict.get("id", ""))
            if nid and nid not in all_nodes:
                all_nodes[nid] = node_dict

        for rel in record["path_rels"]:
            rel_dict = dict(rel)
            src_id = ""
            tgt_id = ""
            # Resolve source/target from the relationship.
            if hasattr(rel, "start_node") and hasattr(rel, "end_node"):
                src_dict = dict(rel.start_node)
                tgt_dict = dict(rel.end_node)
                src_id = src_dict.get("node_id", src_dict.get("id", ""))
                tgt_id = tgt_dict.get("node_id", tgt_dict.get("id", ""))
            edge_key = f"{rel_dict.get('edge_id', '')}:{src_id}:{tgt_id}"
            all_edges.append(
                {
                    "id": edge_key,
                    "source": src_id,
                    "target": tgt_id,
                    "relationship_type": rel_dict.get("relationship_type", ""),
                    "confidence": rel_dict.get("confidence", 0.0),
                    "evidence": rel_dict.get("evidence", []),
                    "discovered_at": rel_dict.get("discovered_at", ""),
                    "method": rel_dict.get("method", ""),
                }
            )

    cyto_nodes = [_node_to_cytoscape(n) for n in all_nodes.values()]
    cyto_edges = [_edge_to_cytoscape(e) for e in all_edges]

    return {"nodes": cyto_nodes, "edges": cyto_edges}


# ── Entity detail (for Task 5.9) ──────────────────────────────────────────────


async def get_entity_detail(
    entity_id: str,
    *,
    investigation_id: str,
    driver: AsyncDriver | None = None,
) -> dict[str, Any] | None:
    """Get full entity details from Neo4j.

    Returns the node properties or None if not found.
    """
    _validate_id(entity_id)
    _validate_id(investigation_id)
    driver = driver or await get_driver()

    query = """
    MATCH (n {id: $entity_id, investigation_id: $investigation_id})
    RETURN
        n.id            AS node_id,
        labels(n)       AS labels,
        n.value         AS value,
        n.confidence    AS confidence,
        n.first_seen    AS first_seen,
        n.last_seen     AS last_seen,
        n.source_count  AS source_count,
        n.properties    AS properties
    """

    async with driver.session() as session:
        result = await session.run(
            query, entity_id=entity_id, investigation_id=investigation_id
        )
        record = await result.single()

    if record is None:
        return None

    result = dict(record)
    props = result.get("properties")
    if isinstance(props, str):
        result["properties"] = json.loads(props)
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────


def _node_to_cytoscape(record: dict[str, Any]) -> dict[str, Any]:
    """Convert a Neo4j node record to Cytoscape.js node element."""
    labels = record.get("labels", [])
    # Use the first (most specific) label as the primary type.
    primary_label = labels[0] if labels else "Unknown"

    data: dict[str, Any] = {
        "id": record.get("node_id", record.get("id", "")),
        "label": record.get("value", ""),
        "type": primary_label,
        "confidence": record.get("confidence", 0.0),
        "first_seen": record.get("first_seen", ""),
        "last_seen": record.get("last_seen", ""),
        "source_count": record.get("source_count", 0),
        "properties": (
            json.loads(record["properties"])
            if isinstance(record.get("properties"), str)
            else record.get("properties", {})
        ),
    }
    return {"data": data}


def _edge_to_cytoscape(record: dict[str, Any]) -> dict[str, Any]:
    """Convert a Neo4j edge record to Cytoscape.js edge element."""
    data: dict[str, Any] = {
        "id": record.get("edge_id", record.get("id", "")),
        "source": record.get("source", ""),
        "target": record.get("target", ""),
        "relationship_type": record.get("relationship_type", ""),
        "confidence": record.get("confidence", 0.0),
        "evidence": record.get("evidence", []),
        "discovered_at": record.get("discovered_at", ""),
        "method": record.get("method", ""),
    }
    return {"data": data}


def _validate_id(value: str) -> None:
    """Basic validation to prevent empty IDs."""
    if not value or not value.strip():
        raise ValueError("ID must be a non-empty string")
