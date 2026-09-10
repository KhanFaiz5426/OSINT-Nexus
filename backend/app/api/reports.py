"""API routes — Reports and AI Analysis.

Phase 8: Real report generation with HTML, PDF, JSON, CSV formats.
Reports use actual stored investigation data — nothing is fabricated.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.security import sanitize_error_message
from app.models import ReportGenerateRequest, ReportResponse

router = APIRouter()


@router.post(
    "/investigations/{investigation_id}/reports",
    response_model=ReportResponse,
)
async def generate_report(
    investigation_id: str,
    body: ReportGenerateRequest | None = None,
) -> ReportResponse:
    """Generate an investigation report in the requested format.

    SECURITY: The investigation_id is validated against the database.
    The format parameter is validated by Pydantic regex. Generated files
    are stored in a dedicated reports_output directory with unique names
    to prevent overwrites and path traversal.
    """
    fmt = body.format if body else "html"

    # Verify investigation exists.
    from app.db.client import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM investigations WHERE id = $1",
            investigation_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    # Aggregate report data from actual stored records.
    from app.services.report_data import collect_report_data

    try:
        data = await collect_report_data(investigation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Investigation data not found") from None

    # Handle STIX format specially
    if fmt == "stix":
        import json

        from app.services.investigation import export_investigation
        from app.services.stix_export import investigation_to_stix_bundle

        inv_data = await export_investigation(investigation_id)
        if inv_data is None:
            raise HTTPException(status_code=404, detail="Investigation data not found")

        stix_bundle = investigation_to_stix_bundle(inv_data)

        # Write STIX bundle to file
        from app.services.report_generator import _REPORTS_DIR

        report_id = str(uuid4())
        file_path = _REPORTS_DIR / f"report_{report_id}.json"

        with open(file_path, "w") as f:
            json.dump(stix_bundle, f, indent=2)

        file_size = file_path.stat().st_size if file_path.exists() else 0

        # Store report metadata
        now = datetime.now(UTC)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO reports (id, investigation_id, format, file_path, file_size, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                report_id,
                investigation_id,
                "stix",
                str(file_path),
                file_size,
                now,
            )

        return ReportResponse(
            id=report_id,
            investigation_id=investigation_id,
            format="stix",
            created_at=now,
            download_url=f"/api/v1/investigations/{investigation_id}/reports/{report_id}",
            file_size=file_size,
        )

    # Generate report file for other formats
    from app.services.report_generator import generate_report as gen

    try:
        file_path = gen(data, fmt)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}") from None
    except Exception as exc:
        safe_msg = sanitize_error_message(exc)
        raise HTTPException(
            status_code=500, detail=f"Report generation failed: {safe_msg}"
        ) from exc

    # Detect actual format from generated file extension.
    # PDF generation may fall back to HTML if WeasyPrint is unavailable.
    actual_ext = os.path.splitext(file_path)[1].lower().strip(".")
    actual_fmt = actual_ext if actual_ext in ("html", "pdf", "json", "csv") else fmt

    # Compute file size.
    try:
        file_size = os.path.getsize(file_path)
    except OSError:
        file_size = 0

    # Store report metadata in database.
    report_id = str(uuid4())
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO reports (id, investigation_id, format, file_path, file_size, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            report_id,
            investigation_id,
            actual_fmt,
            file_path,
            file_size,
            now,
        )

    return ReportResponse(
        id=report_id,
        investigation_id=investigation_id,
        format=actual_fmt,
        created_at=now,
        download_url=f"/api/v1/investigations/{investigation_id}/reports/{report_id}",
        file_size=file_size,
    )


@router.get(
    "/investigations/{investigation_id}/reports/{report_id}",
    response_model=ReportResponse,
)
async def get_report(investigation_id: str, report_id: str) -> ReportResponse:
    """Retrieve report metadata. The actual file is served via /download."""
    from app.db.client import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, investigation_id, format, file_path, file_size, created_at
            FROM reports
            WHERE id = $1 AND investigation_id = $2
            """,
            report_id,
            investigation_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportResponse(
        id=str(row["id"]),
        investigation_id=str(row["investigation_id"]),
        format=row["format"],
        created_at=row["created_at"],
        download_url=f"/api/v1/investigations/{investigation_id}/reports/{report_id}/download",
        file_size=row["file_size"],
    )


@router.get(
    "/investigations/{investigation_id}/reports/{report_id}/download",
)
async def download_report(investigation_id: str, report_id: str) -> FileResponse:
    """Download the actual report file.

    SECURITY: Validates that the report exists, belongs to the investigation,
    and the file path is within the reports_output directory before serving.
    """
    from app.db.client import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, investigation_id, format, file_path
            FROM reports
            WHERE id = $1 AND investigation_id = $2
            """,
            report_id,
            investigation_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")

    file_path = row["file_path"]

    # SECURITY: Validate the file path is within expected directory.
    try:
        from app.services.report_generator import _REPORTS_DIR

        resolved = os.path.realpath(str(file_path))
        reports_dir = os.path.realpath(str(_REPORTS_DIR))
        if not resolved.startswith(reports_dir):
            raise HTTPException(status_code=403, detail="Access denied")

        if not os.path.isfile(resolved):
            raise HTTPException(status_code=404, detail="Report file not found on disk")
    except (OSError, TypeError, ValueError):
        raise HTTPException(status_code=404, detail="Report file not found on disk") from None

    # Determine media type based on actual file extension.
    ext = os.path.splitext(resolved)[1].lower().strip(".")
    if ext == "html":
        media_type = "text/html"
    elif ext == "pdf":
        media_type = "application/pdf"
    elif ext == "json":
        media_type = "application/json"
    elif ext == "csv":
        media_type = "text/csv"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=resolved,
        media_type=media_type,
        filename=f"report_{report_id}.{ext}",
    )


@router.get("/investigations/{investigation_id}/reports")
async def list_reports(investigation_id: str) -> list[ReportResponse]:
    """List all reports for an investigation."""
    from app.db.client import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify investigation exists.
        inv_row = await conn.fetchrow(
            "SELECT id FROM investigations WHERE id = $1",
            investigation_id,
        )
        if inv_row is None:
            raise HTTPException(status_code=404, detail="Investigation not found")

        rows = await conn.fetch(
            """
            SELECT id, investigation_id, format, file_size, created_at
            FROM reports
            WHERE investigation_id = $1
            ORDER BY created_at DESC
            """,
            investigation_id,
        )

    return [
        ReportResponse(
            id=str(row["id"]),
            investigation_id=str(row["investigation_id"]),
            format=row["format"],
            created_at=row["created_at"],
            download_url=f"/api/v1/investigations/{investigation_id}/reports/{row['id']}/download",
            file_size=row["file_size"],
        )
        for row in rows
    ]


@router.get("/investigations/{investigation_id}/ai-analysis")
async def get_ai_analysis(investigation_id: str) -> dict[str, Any]:
    """Get AI analysis for an investigation.

    Returns the latest AI planner and analyzer outputs, along with
    investigation metadata.
    """
    from app.db.client import get_pool
    from app.services.orchestrator import get_graph_summary

    # Verify investigation exists.
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, target, target_type, status, depth,
                   api_calls_used, api_budget, created_at, updated_at
            FROM investigations
            WHERE id = $1
            """,
            investigation_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    # Build graph summary for on-demand analysis.
    graph_summary = await get_graph_summary(investigation_id)

    # Count pivot rounds from activity log.
    pivot_rounds = 0
    try:
        async with pool.acquire() as conn:
            round_row = await conn.fetchrow(
                """
                SELECT COUNT(*) as cnt FROM activity_log
                WHERE investigation_id = $1
                  AND event_type = 'pivot_round_completed'
                """,
                investigation_id,
            )
            if round_row:
                pivot_rounds = round_row["cnt"]
    except Exception:
        pass

    # Run on-demand analysis using configured LLM provider (if any).
    from app.ai.analyzer import analyze_investigation
    from app.ai.client import get_llm_call_fn

    llm_fn = get_llm_call_fn()
    analyzer_output = await analyze_investigation(
        investigation_id=investigation_id,
        target=row["target"],
        target_type=row["target_type"],
        graph_summary=graph_summary,
        pivot_rounds_completed=pivot_rounds,
        llm_call_fn=llm_fn,
    )

    return {
        "investigation_id": investigation_id,
        "analyzer_output": analyzer_output.model_dump() if analyzer_output else None,
        "graph_summary": graph_summary,
        "pivot_rounds_completed": pivot_rounds,
        "generated_at": row["updated_at"].isoformat() if row["updated_at"] else "",
    }
