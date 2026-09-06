"""Investigation service — business logic for investigation CRUD.

Manages investigation lifecycle: creation, retrieval, listing, state transitions.
Uses asyncpg for PostgreSQL operations.
"""

from datetime import UTC, datetime

import asyncpg

from app.db.client import get_pool
from app.models import (
    InvestigationCreate,
    InvestigationDepth,
    InvestigationResponse,
    InvestigationStatus,
    TargetType,
)
from app.services.classifier import classify_target
from app.services.normalizer import normalize_target


async def create_investigation(data: InvestigationCreate) -> InvestigationResponse:
    """Create a new investigation.

    Classifies the target, normalizes it, and stores in PostgreSQL.
    """
    target_type = classify_target(data.target)
    normalized_target = normalize_target(data.target, target_type)
    now = datetime.now(UTC)

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO investigations
                (name, target, target_type, status, depth, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, name, target, target_type, status, depth,
                      created_at, updated_at, api_calls_used, api_budget,
                      entity_count, relationship_count, observation_count
            """,
            data.name,
            normalized_target,
            target_type.value,
            InvestigationStatus.CREATED.value,
            data.depth.value,
            now,
            now,
        )

    return _row_to_response(row)


async def list_investigations(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[InvestigationResponse]:
    """List investigations with optional filtering and pagination."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                """
                SELECT id, name, target, target_type, status, depth,
                       created_at, updated_at, api_calls_used, api_budget,
                       entity_count, relationship_count, observation_count
                FROM investigations
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                status,
                limit,
                offset,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, name, target, target_type, status, depth,
                       created_at, updated_at, api_calls_used, api_budget,
                       entity_count, relationship_count, observation_count
                FROM investigations
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )

    return [_row_to_response(row) for row in rows]


async def get_investigation(investigation_id: str) -> InvestigationResponse | None:
    """Get a single investigation by ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, target, target_type, status, depth, created_at, updated_at,
                   api_calls_used, api_budget, entity_count, relationship_count, observation_count
            FROM investigations
            WHERE id = $1
            """,
            investigation_id,
        )

    if row is None:
        return None

    return _row_to_response(row)


async def stop_investigation(investigation_id: str) -> InvestigationResponse | None:
    """Stop a running investigation by setting its status to 'stopped'."""
    pool = await get_pool()
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE investigations
            SET status = $1, updated_at = $2
            WHERE id = $3 AND status IN ($4, $5)
            RETURNING id, name, target, target_type, status, depth,
                      created_at, updated_at, api_calls_used, api_budget,
                      entity_count, relationship_count, observation_count
            """,
            InvestigationStatus.STOPPED.value,
            now,
            investigation_id,
            InvestigationStatus.CREATED.value,
            InvestigationStatus.RUNNING.value,
        )

    if row is None:
        return None

    return _row_to_response(row)


def _row_to_response(row: asyncpg.Record) -> InvestigationResponse:
    """Convert a database row to an InvestigationResponse."""
    return InvestigationResponse(
        id=str(row["id"]),
        name=row["name"],
        target=row["target"],
        target_type=TargetType(row["target_type"]),
        status=InvestigationStatus(row["status"]),
        depth=InvestigationDepth(row["depth"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        entity_count=row.get("entity_count", 0) or 0,
        relationship_count=row.get("relationship_count", 0) or 0,
        observation_count=row.get("observation_count", 0) or 0,
    )
