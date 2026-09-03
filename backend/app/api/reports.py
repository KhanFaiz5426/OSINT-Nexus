"""API routes — Reports and AI Analysis."""

from fastapi import APIRouter, HTTPException

from app.models import ReportResponse

router = APIRouter()


@router.post("/investigations/{investigation_id}/reports", response_model=ReportResponse)
async def generate_report(investigation_id: str) -> ReportResponse:
    """Generate an investigation report. (Stub — Phase 8 will implement.)"""
    return ReportResponse(
        id="stub",
        investigation_id=investigation_id,
        format="html",
        created_at="2026-01-01T00:00:00Z",
        download_url="/reports/stub",
    )


@router.get(
    "/investigations/{investigation_id}/reports/{report_id}",
    response_model=ReportResponse,
)
async def get_report(investigation_id: str, report_id: str) -> ReportResponse:
    """Download a report. (Stub — Phase 8 will implement.)"""
    return ReportResponse(
        id=report_id,
        investigation_id=investigation_id,
        format="html",
        created_at="2026-01-01T00:00:00Z",
        download_url=f"/reports/{report_id}",
    )


@router.get("/investigations/{investigation_id}/ai-analysis")
async def get_ai_analysis(investigation_id: str) -> dict:
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

    # Run on-demand analysis (with no LLM — returns safe default).
    from app.ai.analyzer import analyze_investigation

    analyzer_output = await analyze_investigation(
        investigation_id=investigation_id,
        target=row["target"],
        target_type=row["target_type"],
        graph_summary=graph_summary,
        pivot_rounds_completed=pivot_rounds,
        llm_call_fn=None,  # On-demand analysis without LLM
    )

    return {
        "investigation_id": investigation_id,
        "analyzer_output": analyzer_output.model_dump() if analyzer_output else None,
        "graph_summary": graph_summary,
        "pivot_rounds_completed": pivot_rounds,
        "generated_at": row["updated_at"].isoformat() if row["updated_at"] else "",
    }
