"""API routes — Investigations."""

import asyncio

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.models import (
    InvestigationCreate,
    InvestigationResponse,
    InvestigationStatus,
    MessageResponse,
)
from app.services.investigation import (
    create_investigation,
    delete_investigation,
    export_investigation,
    get_investigation,
    import_investigation,
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
    # Terminal stop reason (e.g. user_stop, depth_reached, budget_exhausted,
    # no_valid_pivots). None while running or when unknown (legacy rows).
    stop_reason: str | None = None


async def _get_stop_reason(investigation_id: str) -> str | None:
    """Return the latest recorded termination reason, if any.

    Reads the most recent investigation_completed / investigation_stopped
    activity event. Best-effort: returns None when nothing was recorded.
    """
    try:
        from app.db.client import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT details FROM activity_log
                WHERE investigation_id = $1
                  AND event_type IN ('investigation_completed', 'investigation_stopped')
                ORDER BY created_at DESC LIMIT 1
                """,
                investigation_id,
            )
        if row is None:
            return None
        details = row["details"]
        if isinstance(details, str):
            import json as _json

            try:
                details = _json.loads(details)
            except Exception:
                return None
        if isinstance(details, dict):
            reason = details.get("stop_reason")
            return reason if isinstance(reason, str) else None
        return None
    except Exception:
        return None


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
    try:
        return await create_investigation(body)
    except Exception as exc:
        from app.core.security import SSRFBlockedError

        if isinstance(exc, (ValueError, SSRFBlockedError)):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise


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

    Sets the investigation status to 'stopped' and cancels the background task.
    """
    result = await stop_investigation(investigation_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found or not in a stoppable state",
        )

    # Cancel the background TaskManager task so a subsequent re-run can
    # submit the same investigation_id. Cancellation alone is fire-and-forget:
    # the _active_tasks entry is released only when the wrapped coroutine
    # observes CancelledError and moves to history, so await termination
    # (bounded) before returning. Budget is untouched (status-only update).
    from app.core.task_manager import get_task_manager

    tm = get_task_manager()
    info = tm.get_task(investigation_id)
    task = info._asyncio_task if info is not None else None
    is_active = any(t["task_id"] == investigation_id for t in tm.list_active())
    if task is not None and not task.done() and is_active:
        tm.cancel(investigation_id)
        try:
            await asyncio.wait([task], timeout=5.0)
        except Exception:
            pass

    return result


@router.delete(
    "/investigations/{investigation_id}",
    status_code=200,
)
async def delete(investigation_id: str) -> MessageResponse:
    """Delete an investigation and all associated data.

    Permanently removes the investigation, its observations, entities,
    relationships, graph data, reports, and all other dependent data.
    This action cannot be undone.
    """
    try:
        await delete_investigation(investigation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MessageResponse(message=f"Investigation {investigation_id} deleted")


@router.post(
    "/investigations/{investigation_id}/start",
    response_model=InvestigationStartResponse,
)
async def start(investigation_id: str) -> InvestigationStartResponse:
    """Start an investigation — triggers the background collection loop.

    Submits an async task to the TaskManager that runs the full
    investigation pipeline: collect → correlate → AI plan → pivot → ... → stop.
    """
    result = await get_investigation(investigation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    allowed_states = {
        InvestigationStatus.CREATED,
        InvestigationStatus.STOPPED,
        InvestigationStatus.COMPLETED,
        InvestigationStatus.ERROR,
    }
    if result.status not in allowed_states:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot start investigation in '{result.status}' status",
        )

    # Submit to TaskManager.
    from app.core.settings_store import get_app_settings
    from app.core.task_manager import get_task_manager
    from app.tasks.run_investigation import run_investigation_async

    settings = get_app_settings()
    max_concurrent = settings.general.max_concurrent_investigations
    tm = get_task_manager()

    if tm.active_count >= max_concurrent:
        raise HTTPException(
            status_code=429,
            detail=f"Cannot start, {max_concurrent} already running",
        )

    try:
        task_info = tm.submit(
            task_id=investigation_id,
            coro=run_investigation_async(investigation_id),
        )
    except RuntimeError as exc:
        # Duplicate submission (e.g. previous task still releasing) is a
        # client-conflict, not an internal error. Preserve TaskManager's
        # duplicate rejection semantics.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return InvestigationStartResponse(
        message="Investigation started",
        investigation_id=investigation_id,
        task_id=task_info.task_id,
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
        stop_reason=await _get_stop_reason(investigation_id),
    )


# ── Export / Import ─────────────────────────────────────────────────────────


@router.get("/investigations/{investigation_id}/export")
async def export_investigation_data(investigation_id: str) -> JSONResponse:
    """Export an investigation as a JSON bundle.

    Returns the investigation metadata, observations, entities, activity log,
    and graph data as a downloadable JSON file.
    """
    data = await export_investigation(investigation_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": f"attachment; filename=investigation_{investigation_id[:8]}.json"
        },
    )


class ImportRequest(BaseModel):
    """Request body for importing an investigation."""

    data: dict


@router.post("/investigations/import", response_model=InvestigationResponse, status_code=201)
async def import_investigation_data(body: ImportRequest) -> InvestigationResponse:
    """Import an investigation from a JSON bundle.

    Creates a new investigation with the imported data. The original
    investigation ID is not preserved — a new UUID is generated.
    """
    try:
        result = await import_investigation(body.data)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to import investigation: {exc}"
        ) from exc

    if result is None:
        raise HTTPException(status_code=400, detail="Invalid investigation data")

    return result
