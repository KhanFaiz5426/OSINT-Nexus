"""Workspace Management API.

Exposes endpoints for the WorkspaceManager to coordinate opening, closing,
and creating .osint investigation databases safely.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.workspace import (
    WorkspaceConflictError,
    WorkspaceError,
    WorkspaceValidationError,
    get_workspace_manager,
)
from app.models import ReportGenerateRequest, ReportResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspace", tags=["workspace"])


class WorkspacePathRequest(BaseModel):
    path: str


class WorkspaceStatusResponse(BaseModel):
    active_workspace: str | None


@router.get("/status", response_model=WorkspaceStatusResponse)
async def get_status() -> WorkspaceStatusResponse:
    """Get the currently active workspace path."""
    wm = get_workspace_manager()
    return WorkspaceStatusResponse(active_workspace=wm.current_workspace)


@router.post("/new", response_model=WorkspaceStatusResponse)
async def create_new(request: WorkspacePathRequest) -> WorkspaceStatusResponse:
    """Create a new workspace at the given path."""
    wm = get_workspace_manager()
    try:
        await wm.create_new(request.path)
        return WorkspaceStatusResponse(active_workspace=wm.current_workspace)
    except WorkspaceConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except WorkspaceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except WorkspaceError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/open", response_model=WorkspaceStatusResponse)
async def open_workspace(request: WorkspacePathRequest) -> WorkspaceStatusResponse:
    """Open an existing workspace safely."""
    wm = get_workspace_manager()
    try:
        await wm.open_workspace(request.path)
        return WorkspaceStatusResponse(active_workspace=wm.current_workspace)
    except WorkspaceConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except WorkspaceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except WorkspaceError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/save-as", response_model=WorkspaceStatusResponse)
async def save_as(request: WorkspacePathRequest) -> WorkspaceStatusResponse:
    """Save a snapshot of the current workspace to a new file."""
    wm = get_workspace_manager()
    try:
        await wm.save_as(request.path)
        return WorkspaceStatusResponse(active_workspace=wm.current_workspace)
    except WorkspaceConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except WorkspaceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except WorkspaceError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/close", response_model=WorkspaceStatusResponse)
async def close_workspace() -> WorkspaceStatusResponse:
    """Close the current workspace safely."""
    wm = get_workspace_manager()
    try:
        await wm.close_workspace()
        return WorkspaceStatusResponse(active_workspace=wm.current_workspace)
    except WorkspaceError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/reports", response_model=ReportResponse)
async def generate_workspace_report(
    body: ReportGenerateRequest | None = None,
) -> ReportResponse:
    """Generate a workspace-level report in the requested format."""
    fmt = body.format if body else "html"

    # We must ensure there is an active workspace first
    wm = get_workspace_manager()
    if not wm.current_workspace:
        raise HTTPException(status_code=400, detail="No workspace open")

    from app.services.report_data import collect_workspace_report_data

    try:
        data = await collect_workspace_report_data()
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to collect workspace data: {exc}"
        ) from exc

    from app.core.security import sanitize_error_message
    from app.services.report_generator import generate_report as gen

    # Ensure data is flagged as a workspace report for the generator
    data["is_workspace_report"] = True

    try:
        file_path = gen(data, fmt)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}") from None
    except Exception as exc:
        safe_msg = sanitize_error_message(exc)
        raise HTTPException(
            status_code=500, detail=f"Workspace report generation failed: {safe_msg}"
        ) from exc

    actual_ext = os.path.splitext(file_path)[1].lower().strip(".")
    actual_fmt = actual_ext if actual_ext in ("html", "json", "csv") else fmt

    try:
        file_size = os.path.getsize(file_path)
    except OSError:
        file_size = 0

    report_id = str(uuid4())
    now = datetime.now(UTC)

    from app.db.client import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO workspace_reports (id, format, file_path, file_size, created_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            report_id,
            actual_fmt,
            file_path,
            file_size,
            now,
        )

    return ReportResponse(
        id=report_id,
        investigation_id="workspace",
        format=actual_fmt,
        created_at=now,
        download_url=f"/api/v1/workspace/reports/{report_id}/download",
        file_size=file_size,
    )


@router.get("/reports/{report_id}/download")
async def download_workspace_report(report_id: str) -> FileResponse:
    """Download the actual workspace report file."""
    from app.db.client import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, format, file_path
            FROM workspace_reports
            WHERE id = $1
            """,
            report_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="Workspace report not found")

    file_path = row["file_path"]

    try:
        from app.services.report_generator import _REPORTS_DIR

        resolved = os.path.realpath(str(file_path))
        reports_dir = os.path.realpath(str(_REPORTS_DIR))

        import os as _os

        if _os.name == "nt":
            if not resolved.lower().startswith(reports_dir.lower()):
                raise HTTPException(status_code=403, detail="Access denied")
        else:
            if not resolved.startswith(reports_dir):
                raise HTTPException(status_code=403, detail="Access denied")

        if not os.path.isfile(resolved):
            raise HTTPException(status_code=404, detail="Report file not found on disk")
    except (OSError, TypeError, ValueError):
        raise HTTPException(status_code=404, detail="Report file not found on disk") from None

    ext = os.path.splitext(resolved)[1].lower().strip(".")
    if ext == "html":
        media_type = "text/html"

    elif ext == "json":
        media_type = "application/json"
    elif ext == "csv":
        media_type = "text/csv"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=resolved,
        media_type=media_type,
        filename=f"workspace_report_{report_id}.{ext}",
    )
