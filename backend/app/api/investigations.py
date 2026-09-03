"""API routes — Investigations."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models import (
    InvestigationCreate,
    InvestigationResponse,
    InvestigationStatus,
)
from app.services.investigation import (
    create_investigation,
    get_investigation,
    list_investigations,
    stop_investigation,
)

router = APIRouter()


# ── Response models for start/status ─────────────────────────────────────────


class InvestigationStatusResponse(BaseModel):
    """Detailed investigation status response."""

    id: str
    status: str
    target: str
    target_type: str
    depth: str
    api_calls_used: int = 0
    api_budget: int = 100
    entity_count: int = 0
    relationship_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class InvestigationStartResponse(BaseModel):
    """Response when an investigation is started."""

    message: str
    investigation_id: str
    task_id: str = ""


@router.post("/investigations", response_model=InvestigationResponse, status_code=201)
async def create(body: InvestigationCreate) -> InvestigationResponse:
    """Create a new investigation.

    Accepts a target (domain, IP, URL, email, username, or organization),
    classifies the target type, normalizes the input, and stores the investigation.
    """
    return await create_investigation(body)


@router.get("/investigations", response_model=list[InvestigationResponse])
async def list_all(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[InvestigationResponse]:
    """List all investigations with optional filtering and pagination."""
    return await list_investigations(status=status, limit=limit, offset=offset)


@router.get("/investigations/{investigation_id}", response_model=InvestigationResponse)
async def get_one(investigation_id: str) -> InvestigationResponse:
    """Get investigation details by ID."""
    result = await get_investigation(investigation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return result


@router.post(
    "/investigations/{investigation_id}/stop",
    response_model=InvestigationResponse,
)
async def stop(investigation_id: str) -> InvestigationResponse:
    """Stop a running investigation.

    Sets the investigation status to 'stopped'. Only works for investigations
    in 'created' or 'running' status.
    """
    result = await stop_investigation(investigation_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found or not in a stoppable state",
        )
    return result


@router.post(
    "/investigations/{investigation_id}/start",
    response_model=InvestigationStartResponse,
)
async def start(investigation_id: str) -> InvestigationStartResponse:
    """Start an investigation — triggers the background collection loop.

    Launches a Celery task that runs the full investigation pipeline:
    collect → correlate → AI plan → pivot → ... → stop.
    """
    result = await get_investigation(investigation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    if result.status not in (InvestigationStatus.CREATED,):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot start investigation in '{result.status}' status",
        )

    # Launch Celery task.
    from app.tasks.run_investigation import run_investigation_task

    task = run_investigation_task.delay(investigation_id)

    return InvestigationStartResponse(
        message="Investigation started",
        investigation_id=investigation_id,
        task_id=task.id,
    )


@router.get(
    "/investigations/{investigation_id}/status",
    response_model=InvestigationStatusResponse,
)
async def get_status(investigation_id: str) -> InvestigationStatusResponse:
    """Get detailed investigation status including budget and counts."""
    result = await get_investigation(investigation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    # Get entity and relationship counts from graph.
    entity_count = 0
    relationship_count = 0
    try:
        from app.graph.reader import get_investigation_subgraph

        graph = await get_investigation_subgraph(investigation_id)
        entity_count = len(graph.get("nodes", []))
        relationship_count = len(graph.get("edges", []))
    except Exception:
        pass

    # Get budget info from DB.
    api_calls_used = 0
    api_budget = 100
    try:
        from app.db.client import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT api_calls_used, api_budget FROM investigations WHERE id = $1",
                investigation_id,
            )
            if row:
                api_calls_used = row["api_calls_used"]
                api_budget = row["api_budget"]
    except Exception:
        pass

    return InvestigationStatusResponse(
        id=result.id,
        status=result.status.value,
        target=result.target,
        target_type=result.target_type.value,
        depth=result.depth.value,
        api_calls_used=api_calls_used,
        api_budget=api_budget,
        entity_count=entity_count,
        relationship_count=relationship_count,
        created_at=result.created_at.isoformat() if result.created_at else "",
        updated_at=result.updated_at.isoformat() if result.updated_at else "",
    )
