"""Graph reader - query SQLite for investigation subgraphs, neighbors, paths (Migrated in Phase 3)."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.db.client import get_pool

logger = logging.getLogger(__name__)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _node_to_cytoscape(record: dict[str, Any]) -> dict[str, Any]:
    """Convert a SQLite entity record to Cytoscape.js node element."""
    primary_label = record.get("type", "Unknown")

    properties = record.get("properties", {})
    if isinstance(properties, str):
        try:
            properties = json.loads(properties) if properties else {}
        except Exception:
            properties = {}
    if not isinstance(properties, dict):
        properties = {}

    sources = record.get("sources") or properties.get("_sources", [])
    if isinstance(sources, str):
        sources = [s for s in sources.split(",") if s]
    if sources:
        properties["sources"] = list(sources)

    data: dict[str, Any] = {
        "id": record.get("node_id", record.get("id", "")),
        "label": record.get("value", ""),
        "type": primary_label,
        "confidence": record.get("confidence", 0.0),
        "first_seen": record.get("first_seen", ""),
        "last_seen": record.get("last_seen", ""),
        "source_count": record.get("source_count", 0) or len(sources),
        "sources": sources,
        "properties": properties,
    }
    return {"data": data}


def _edge_to_cytoscape(record: dict[str, Any]) -> dict[str, Any]:
    """Convert a SQLite relationship record to Cytoscape.js edge element."""
    evidence = record.get("evidence", [])
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence) if evidence else []
        except Exception:
            evidence = []
            
    data: dict[str, Any] = {
        "id": record.get("edge_id", record.get("id", "")),
        "source": record.get("source_id", record.get("source", "")),
        "target": record.get("target_id", record.get("target", "")),
        "relationship_type": record.get("relationship_type", ""),
        "confidence": record.get("confidence", 0.0),
        "evidence": evidence,
        "discovered_at": record.get("discovered_at", ""),
        "method": record.get("method", ""),
    }
    return {"data": data}


def _validate_id(value: str) -> None:
    if not value or not value.strip():
        raise ValueError("ID must be a non-empty string")


# ─── Investigation subgraph ───────────────────────────────────────────────────


async def get_investigation_subgraph(
    investigation_id: str,
    *,
    limit: int | None = None,
    offset: int = 0,
    entity_type_filter: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    _validate_id(investigation_id)
    pool = await get_pool()

    nodes_query = """
    SELECT id AS node_id, * FROM entities
    WHERE investigation_id = $1
    """
    params = [investigation_id]

    if entity_type_filter:
        nodes_query += " AND type = $2"
        params.append(entity_type_filter)
        
    if limit is not None:
        nodes_query += f" LIMIT {limit} OFFSET {offset}"

    edges_query = """
    SELECT id AS edge_id, source_id AS source, target_id AS target, * FROM relationships
    WHERE investigation_id = $1
    """

    async with pool.acquire() as conn:
        nodes = await conn.fetch(nodes_query, *params)
        edges = await conn.fetch(edges_query, investigation_id)

    cyto_nodes = [_node_to_cytoscape(dict(n)) for n in nodes]
    cyto_edges = [_edge_to_cytoscape(dict(e)) for e in edges]

    logger.info("Retrieved subgraph for %s: %d nodes, %d edges", investigation_id, len(cyto_nodes), len(cyto_edges))
    return {"nodes": cyto_nodes, "edges": cyto_edges}


async def get_investigation_graph_stats(
    investigation_id: str) -> dict[str, int]:
    _validate_id(investigation_id)
    pool = await get_pool()

    async with pool.acquire() as conn:
        n = await conn.fetch("SELECT COUNT(*) as count FROM entities WHERE investigation_id = $1", investigation_id)
        e = await conn.fetch("SELECT COUNT(*) as count FROM relationships WHERE investigation_id = $1", investigation_id)

    return {
        "total_nodes": n[0]["count"] if n else 0,
        "total_edges": e[0]["count"] if e else 0,
    }


# ─── Entity neighbors ─────────────────────────────────────────────────────────


async def get_entity_neighbors(
    entity_id: str,
    *,
    investigation_id: str,
    max_depth: int = 1,
) -> dict[str, list[dict[str, Any]]]:
    _validate_id(entity_id)
    _validate_id(investigation_id)
    pool = await get_pool()

    max_depth = max(1, min(max_depth, 6))

    cte = f"""
    WITH RECURSIVE traverse(node_id, depth, path) AS (
        SELECT $1, 0, ',' || $1 || ','
        UNION ALL
        SELECT e.to_id, t.depth + 1, t.path || e.to_id || ','
        FROM edges_bidi e
        JOIN traverse t ON e.from_id = t.node_id
        WHERE e.investigation_id = $2
          AND t.depth < $3
          AND t.path NOT LIKE '%,' || e.to_id || ',%'
    )
    SELECT DISTINCT node_id FROM traverse LIMIT 1000
    """

    async with pool.acquire() as conn:
        node_ids_records = await conn.fetch(cte, entity_id, investigation_id, max_depth)
        
        if not node_ids_records:
            return {"nodes": [], "edges": []}
            
        # SQLite IN clause limitation bypass (Phase 2 json_each trick)
        ids_json = json.dumps([r["node_id"] for r in node_ids_records])
        
        nodes_q = "SELECT id AS node_id, * FROM entities WHERE investigation_id = $1 AND id IN (SELECT value FROM json_each($2))"
        nodes = await conn.fetch(nodes_q, investigation_id, ids_json)
        
        edges_q = """
        SELECT id AS edge_id, source_id AS source, target_id AS target, * FROM relationships 
        WHERE investigation_id = $1 
          AND source_id IN (SELECT value FROM json_each($2))
          AND target_id IN (SELECT value FROM json_each($2))
        """
        edges = await conn.fetch(edges_q, investigation_id, ids_json)

    cyto_nodes = [_node_to_cytoscape(dict(n)) for n in nodes]
    cyto_edges = [_edge_to_cytoscape(dict(e)) for e in edges]

    return {"nodes": cyto_nodes, "edges": cyto_edges}


# ─── Multi-hop paths ──────────────────────────────────────────────────────────


async def get_multi_hop_paths(
    source_id: str,
    target_id: str,
    *,
    investigation_id: str,
    max_hops: int = 4,
) -> dict[str, list[dict[str, Any]]]:
    _validate_id(source_id)
    _validate_id(target_id)
    _validate_id(investigation_id)
    pool = await get_pool()

    max_hops = max(1, min(max_hops, 10))

    # To find ALL paths between source and target, we trace paths from source.
    # We collect paths that reach the target.
    # Then we extract all unique nodes and edges from those paths.
    cte = f"""
    WITH RECURSIVE traverse(node_id, depth, path) AS (
        SELECT $1, 0, ',' || $1 || ','
        UNION ALL
        SELECT e.to_id, t.depth + 1, t.path || e.to_id || ','
        FROM edges_bidi e
        JOIN traverse t ON e.from_id = t.node_id
        WHERE e.investigation_id = $3
          AND t.depth < $4
          AND t.path NOT LIKE '%,' || e.to_id || ',%'
    )
    SELECT path FROM traverse WHERE node_id = $2 LIMIT 10
    """

    async with pool.acquire() as conn:
        paths = await conn.fetch(cte, source_id, target_id, investigation_id, max_hops)
        
        if not paths:
            return {"nodes": [], "edges": []}
            
        unique_nodes = set()
        for p in paths:
            nodes = [n for n in p["path"].split(",") if n]
            unique_nodes.update(nodes)
            
        ids_json = json.dumps(list(unique_nodes))
        
        nodes_q = "SELECT id AS node_id, * FROM entities WHERE investigation_id = $1 AND id IN (SELECT value FROM json_each($2))"
        nodes_records = await conn.fetch(nodes_q, investigation_id, ids_json)
        
        edges_q = """
        SELECT id AS edge_id, source_id AS source, target_id AS target, * FROM relationships 
        WHERE investigation_id = $1 
          AND source_id IN (SELECT value FROM json_each($2))
          AND target_id IN (SELECT value FROM json_each($2))
        """
        edges_records = await conn.fetch(edges_q, investigation_id, ids_json)

    cyto_nodes = [_node_to_cytoscape(dict(n)) for n in nodes_records]
    cyto_edges = [_edge_to_cytoscape(dict(e)) for e in edges_records]

    return {"nodes": cyto_nodes, "edges": cyto_edges}


# ─── Entity detail ────────────────────────────────────────────────────────────


async def get_entity_detail(
    entity_id: str,
    *,
    investigation_id: str,
) -> dict[str, Any] | None:
    _validate_id(entity_id)
    _validate_id(investigation_id)
    pool = await get_pool()

    async with pool.acquire() as conn:
        r = await conn.fetch(
            "SELECT id AS node_id, * FROM entities WHERE id = $1 AND investigation_id = $2",
            entity_id, investigation_id
        )
        
    if not r:
        return None
        
    d = dict(r[0])
    props = d.get("properties")
    if isinstance(props, str):
        try:
            d["properties"] = json.loads(props)
        except:
            d["properties"] = {}
    return d
