"""Workspace Management API.

Exposes endpoints for the WorkspaceManager to coordinate opening, closing,
and creating .osint investigation databases safely.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.workspace import (
    WorkspaceConflictError,
    WorkspaceError,
    WorkspaceManager,
    WorkspaceValidationError,
    get_workspace_manager,
)

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
    except WorkspaceConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except WorkspaceError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
