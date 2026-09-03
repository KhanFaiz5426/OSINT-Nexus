"""API routes — Knowledge Graph.

Task 5.8: GET /investigations/{id}/graph — return nodes + edges for Cytoscape.js.
"""

from fastapi import APIRouter, HTTPException, Query

from app.db.client import get_pool
from app.graph.reader import get_entity_neighbors, get_investigation_subgraph
from app.models import GraphResponse

router = APIRouter()


@router.get("/investigations/{investigation_id}/graph", response_model=GraphResponse)
async def get_investigation_graph(
    investigation_id: str,
    entity_id: str | None = Query(
        None,
        description="If set, return neighbors of this entity instead of the full graph",
    ),
    depth: int = Query(1, ge=1, le=6, description="Neighbor traversal depth"),
) -> GraphResponse:
    """Get knowledge graph for an investigation.

    Returns all nodes and edges in Cytoscape.js-compatible format.
    Optionally filters to neighbors of a specific entity.

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
        else:
            result = await get_investigation_subgraph(investigation_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to query knowledge graph"
        ) from exc

    return GraphResponse(nodes=result["nodes"], edges=result["edges"])


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
