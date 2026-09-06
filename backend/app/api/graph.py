"""API routes — Knowledge Graph.

Task 5.8: GET /investigations/{id}/graph — return nodes + edges for Cytoscape.js.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.db.client import get_pool
from app.graph.reader import (
    get_entity_neighbors,
    get_investigation_graph_stats,
    get_investigation_subgraph,
)
from app.models import GraphResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/investigations/{investigation_id}/graph", response_model=GraphResponse)
async def get_investigation_graph(
    investigation_id: str,
    entity_id: str | None = Query(
        None,
        description="If set, return neighbors of this entity instead of the full graph",
    ),
    depth: int = Query(1, ge=1, le=6, description="Neighbor traversal depth"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum nodes to return (pagination)"
    ),
    offset: int = Query(0, ge=0, description="Number of nodes to skip (pagination)"),
    entity_type: str | None = Query(
        None, description="Filter by entity type (e.g., Domain, IP, Email)"
    ),
) -> GraphResponse:
    """Get knowledge graph for an investigation.

    Returns all nodes and edges in Cytoscape.js-compatible format.
    Optionally filters to neighbors of a specific entity.
    Supports pagination via limit/offset and entity type filtering.

    Investigation ID is validated against PostgreSQL to enforce boundaries.
    """
    # Validate investigation exists.
    await _validate_investigation(investigation_id)

    try:
        if entity_id:
            result = await get_entity_neighbors(
                entity_id,
                investigation_id=investigation_id,
                max_depth=depth,
            )
            # For neighbor queries, total counts are not paginated
            return GraphResponse(nodes=result["nodes"], edges=result["edges"])

        # Get total counts for pagination metadata
        stats = await get_investigation_graph_stats(investigation_id)

        result = await get_investigation_subgraph(
            investigation_id,
            limit=limit,
            offset=offset,
            entity_type_filter=entity_type,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to query knowledge graph for %s", investigation_id)
        raise HTTPException(
            status_code=500, detail=f"Failed to query knowledge graph: {exc}"
        ) from exc

    return GraphResponse(
        nodes=result["nodes"],
        edges=result["edges"],
        total_nodes=stats["total_nodes"],
        total_edges=stats["total_edges"],
    )


@router.get(
    "/investigations/{investigation_id}/graph/paths",
    response_model=GraphResponse,
)
async def get_graph_paths(
    investigation_id: str,
    source_id: str = Query(..., description="Source entity ID"),
    target_id: str = Query(..., description="Target entity ID"),
    max_hops: int = Query(4, ge=1, le=10, description="Maximum path length"),
) -> GraphResponse:
    """Find multi-hop paths between two entities in the investigation graph.

    Returns all nodes and edges on paths between source and target.
    """
    await _validate_investigation(investigation_id)

    from app.graph.reader import get_multi_hop_paths

    try:
        result = await get_multi_hop_paths(
            source_id,
            target_id,
            investigation_id=investigation_id,
            max_hops=max_hops,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to query graph paths"
        ) from exc

    return GraphResponse(nodes=result["nodes"], edges=result["edges"])


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
