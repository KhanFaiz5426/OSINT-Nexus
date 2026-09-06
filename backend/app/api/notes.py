"""API routes — Analyst Notes and Annotations.

Provides CRUD endpoints for notes attached to investigations and entities.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.client import get_pool
from app.models import MessageResponse

router = APIRouter()


class NoteCreate(BaseModel):
    """Request model for creating a note."""

    content: str = Field(..., min_length=1, max_length=10000, description="Note content")
    entity_id: str | None = Field(
        None, description="Entity ID (None for investigation-level note)"
    )


class NoteUpdate(BaseModel):
    """Request model for updating a note."""

    content: str = Field(..., min_length=1, max_length=10000, description="Updated content")


class NoteResponse(BaseModel):
    """Response model for a note."""

    id: str
    investigation_id: str
    entity_id: str | None
    content: str
    created_at: str
    updated_at: str


@router.get(
    "/investigations/{investigation_id}/notes",
    response_model=list[NoteResponse],
)
async def list_notes(
    investigation_id: str,
    entity_id: str | None = Query(None, description="Filter by entity ID"),
) -> list[NoteResponse]:
    """List all notes for an investigation, optionally filtered by entity."""
    await _validate_investigation(investigation_id)

    pool = await get_pool()
    async with pool.acquire() as conn:
        if entity_id:
            rows = await conn.fetch(
                """
                SELECT id, investigation_id, entity_id, content, created_at, updated_at
                FROM notes
                WHERE investigation_id = $1 AND entity_id = $2
                ORDER BY created_at DESC
                """,
                investigation_id,
                entity_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, investigation_id, entity_id, content, created_at, updated_at
                FROM notes
                WHERE investigation_id = $1
                ORDER BY created_at DESC
                """,
                investigation_id,
            )

    return [_row_to_note(row) for row in rows]


@router.post(
    "/investigations/{investigation_id}/notes",
    response_model=NoteResponse,
    status_code=201,
)
async def create_note(
    investigation_id: str,
    body: NoteCreate,
) -> NoteResponse:
    """Create a new note for an investigation or entity."""
    await _validate_investigation(investigation_id)

    note_id = str(uuid4())
    now = datetime.now(UTC)

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO notes (id, investigation_id, entity_id, content, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            note_id,
            investigation_id,
            body.entity_id,
            body.content,
            now,
            now,
        )

    return NoteResponse(
        id=note_id,
        investigation_id=investigation_id,
        entity_id=body.entity_id,
        content=body.content,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )


@router.put(
    "/investigations/{investigation_id}/notes/{note_id}",
    response_model=NoteResponse,
)
async def update_note(
    investigation_id: str,
    note_id: str,
    body: NoteUpdate,
) -> NoteResponse:
    """Update an existing note."""
    await _validate_investigation(investigation_id)

    now = datetime.now(UTC)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE notes
            SET content = $1, updated_at = $2
            WHERE id = $3 AND investigation_id = $4
            RETURNING id, investigation_id, entity_id, content, created_at, updated_at
            """,
            body.content,
            now,
            note_id,
            investigation_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="Note not found")

    return _row_to_note(row)


@router.delete(
    "/investigations/{investigation_id}/notes/{note_id}",
    response_model=MessageResponse,
)
async def delete_note(
    investigation_id: str,
    note_id: str,
) -> MessageResponse:
    """Delete a note."""
    await _validate_investigation(investigation_id)

    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM notes
            WHERE id = $1 AND investigation_id = $2
            """,
            note_id,
            investigation_id,
        )

    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Note not found")

    return MessageResponse(message="Note deleted")


# ── Helpers ───────────────────────────────────────────────────────────────────


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


def _row_to_note(row) -> NoteResponse:
    """Convert a database row to a NoteResponse."""
    return NoteResponse(
        id=str(row["id"]),
        investigation_id=str(row["investigation_id"]),
        entity_id=row["entity_id"],
        content=row["content"],
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else "",
    )
