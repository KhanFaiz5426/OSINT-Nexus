"""API routes — Activity log and observations timeline.

Phase 7 support:
- GET /investigations/{id}/activity — list activity log entries
- GET /investigations/{id}/observations — list raw observations (timeline)
"""

from __future__ import annotations

import contextlib
import json

from fastapi import APIRouter, HTTPException, Query

from app.db.client import get_pool

router = APIRouter()


@router.get("/investigations/{investigation_id}/activity")
async def list_activity(
    investigation_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """List activity log entries for an investigation.

    Returns events in chronological order (most recent first).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        inv_row = await conn.fetchrow(
            "SELECT id FROM investigations WHERE id = $1",
            investigation_id,
        )
        if inv_row is None:
            raise HTTPException(status_code=404, detail="Investigation not found")

        rows = await conn.fetch(
            """
            SELECT id, event_type, details, created_at
            FROM activity_log
            WHERE investigation_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            investigation_id,
            limit,
            offset,
        )

    return {
        "items": [
            {
                "id": int(row["id"]),
                "event_type": row["event_type"],
                "details": _safe_json(row["details"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else "",
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/investigations/{investigation_id}/observations")
async def list_observations(
    investigation_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """List raw observations for an investigation (timeline source)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        inv_row = await conn.fetchrow(
            "SELECT id FROM investigations WHERE id = $1",
            investigation_id,
        )
        if inv_row is None:
            raise HTTPException(status_code=404, detail="Investigation not found")

        rows = await conn.fetch(
            """
            SELECT id, source_adapter, source_version, collected_at,
                   method, target, raw_response, normalized_value,
                   confidence, status, error_message
            FROM observations
            WHERE investigation_id = $1
            ORDER BY collected_at DESC
            LIMIT $2 OFFSET $3
            """,
            investigation_id,
            limit,
            offset,
        )

    return {
        "items": [
            {
                "id": str(row["id"]),
                "source_adapter": row["source_adapter"],
                "source_version": row.get("source_version", ""),
                "collected_at": row["collected_at"].isoformat() if row["collected_at"] else "",
                "method": row["method"],
                "target": row["target"],
                "raw_response": _safe_json(row["raw_response"]),
                "normalized_value": row.get("normalized_value", ""),
                "confidence": row.get("confidence", 0.0),
                "status": row.get("status", "success"),
                "error_message": row.get("error_message", ""),
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
    }


def _safe_json(value) -> dict:
    """Convert a value to a JSON-safe dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            return json.loads(value)
        return {"_raw": value}
    if value is None:
        return {}
    return {"_raw": str(value)}
