"""Investigation service — business logic for investigation CRUD.

Manages investigation lifecycle: creation, retrieval, listing, state transitions.
Uses asyncpg for PostgreSQL operations.
"""

import json
import logging
import uuid
from datetime import UTC, datetime

import aiosqlite

from app.db.client import get_pool
from app.models import (
    EntityType,
    InvestigationCreate,
    InvestigationDepth,
    InvestigationResponse,
    InvestigationStatus,
    RelationshipType,
    TargetType,
)
from app.services.classifier import classify_target
from app.services.normalizer import normalize_target

logger = logging.getLogger(__name__)


async def create_investigation(data: InvestigationCreate) -> InvestigationResponse:
    """Create a new investigation.

    Classifies the target, normalizes it, and stores in PostgreSQL.
    When the caller does not explicitly choose a depth (i.e. uses the
    default ``STANDARD``), the runtime setting ``general.default_depth``
    is applied instead.
    """
    from app.core.security import validate_target_for_collector

    target_type = data.target_type if data.target_type is not None else classify_target(data.target)
    normalized_target = normalize_target(data.target, target_type)
    validate_target_for_collector(normalized_target, target_type.value)

    now = datetime.now(UTC)

    # Apply default depth from settings store only when the caller did not
    # explicitly provide a depth. An explicit value (including STANDARD) is
    # authoritative. Only applies when a settings file exists on disk.
    depth = data.depth
    if depth is None:
        depth = InvestigationDepth.STANDARD
        try:
            from app.core.settings_store import SETTINGS_FILE, get_app_settings

            if SETTINGS_FILE.exists():
                settings = get_app_settings()
                depth = InvestigationDepth(settings.general.default_depth)
        except Exception:
            pass

    # Apply default API budget from settings store.
    try:
        from app.core.settings_store import SETTINGS_FILE, get_app_settings

        api_budget = get_app_settings().investigation.api_budget if SETTINGS_FILE.exists() else 100
    except Exception:
        api_budget = 100

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO investigations
                (id, name, target, target_type, status, depth, api_budget, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id, name, target, target_type, status, depth,
                      created_at, updated_at, api_calls_used, api_budget,
                      entity_count, relationship_count, observation_count
            """,
            str(uuid.uuid4()),
            data.name,
            normalized_target,
            target_type.value,
            InvestigationStatus.CREATED.value,
            depth.value,
            api_budget,
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
    """Stop a running investigation by setting its status to 'stopped'.

    Records an ``investigation_stopped`` activity event with stop reason
    ``user_stop`` so the termination reason stays distinguishable from
    orchestrator-driven stops (depth_reached, budget_exhausted, ...).
    """
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

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO activity_log (investigation_id, event_type, details)
                VALUES ($1, $2, $3)
                """,
                investigation_id,
                "investigation_stopped",
                json.dumps({"stop_reason": "user_stop"}),
            )
    except Exception:
        logger.warning("Failed to log user stop for %s", investigation_id)

    return _row_to_response(row)


def _row_to_response(row: aiosqlite.Row) -> InvestigationResponse:
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


async def delete_investigation(investigation_id: str) -> bool:
    """Delete an investigation and all its associated data.

    Deletion order (safe and transactional):
    1. Verify investigation exists and is not running.
    2. Capture report file paths before DB deletion.
    3. Delete graph investigation-scoped data.
    4. Delete PostgreSQL investigation data (cascades to all child tables).
    5. Delete report files from disk after successful DB/graph deletion.

    If any critical step fails, the function raises an exception rather than
    leaving the investigation partially deleted.

    Returns:
        True if deletion was successful.

    Raises:
        ValueError: If investigation does not exist.
        RuntimeError: If investigation is currently running.
        RuntimeError: If deletion fails at any critical step.
    """
    from pathlib import Path

    pool = await get_pool()

    # Step 1: Verify investigation exists and is not running.
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, status FROM investigations WHERE id = $1",
            investigation_id,
        )
        if row is None:
            raise ValueError(f"Investigation {investigation_id} not found")

        if row["status"] == InvestigationStatus.RUNNING.value:
            raise RuntimeError("Cannot delete a running investigation. Stop it first.")

    # Step 2: Capture report file paths before DB deletion.
    report_file_paths: list[str] = []
    try:
        async with pool.acquire() as conn:
            report_rows = await conn.fetch(
                "SELECT file_path FROM reports WHERE investigation_id = $1",
                investigation_id,
            )
            report_file_paths = [str(r["file_path"]) for r in report_rows if r["file_path"]]
    except Exception:
        logger.warning("Failed to capture report file paths for %s", investigation_id)

    # Step 3: Delete graph investigation-scoped data.
    try:
        from app.graph.writer import delete_investigation_graph

        await delete_investigation_graph(investigation_id)
    except Exception as exc:
        logger.warning(
            "Failed to delete graph data for %s (proceeding with DB deletion): %s",
            investigation_id,
            exc,
        )

    # Step 4: Delete PostgreSQL investigation data (cascades to all child tables).
    try:
        async with pool.acquire() as conn:
            deleted = await conn.execute(
                "DELETE FROM investigations WHERE id = $1",
                investigation_id,
            )
            if deleted == "DELETE 0":
                raise RuntimeError(f"PostgreSQL deletion returned 0 rows for {investigation_id}")
    except Exception as exc:
        raise RuntimeError(f"Failed to delete investigation from database: {exc}") from exc

    # Step 5: Delete report files from disk (only after successful DB deletion).
    deleted_files = 0
    for file_path in report_file_paths:
        try:
            p = Path(file_path)
            if p.is_file():
                p.unlink()
                deleted_files += 1
        except Exception as exc:
            logger.warning("Failed to delete report file %s: %s", file_path, exc)

    logger.info(
        "Deleted investigation %s: %d report files cleaned up",
        investigation_id,
        deleted_files,
    )
    return True


async def export_investigation(investigation_id: str) -> dict | None:
    """Export an investigation as a JSON-serializable dict.

    Includes the investigation metadata, all observations, entities, and graph data.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get investigation
        inv_row = await conn.fetchrow(
            """
            SELECT id, name, target, target_type, status, depth,
                   api_calls_used, api_budget, entity_count, relationship_count,
                   observation_count, created_at, updated_at
            FROM investigations WHERE id = $1
            """,
            investigation_id,
        )
        if inv_row is None:
            return None

        # Get observations
        obs_rows = await conn.fetch(
            """
            SELECT id, source_adapter, source_version, collected_at, method,
                   target, raw_response, normalized_value, confidence, status
            FROM observations
            WHERE investigation_id = $1
            ORDER BY collected_at
            """,
            investigation_id,
        )

        # Get entities
        entity_rows = await conn.fetch(
            """
            SELECT id, type, value, confidence, first_seen, last_seen,
                   source_count, properties
            FROM entities
            WHERE investigation_id = $1
            """,
            investigation_id,
        )

        # Get activity log
        activity_rows = await conn.fetch(
            """
            SELECT event_type, details, created_at
            FROM activity_log
            WHERE investigation_id = $1
            ORDER BY created_at
            """,
            investigation_id,
        )

    # Get graph data
    graph_data = {"nodes": [], "edges": []}
    try:
        from app.graph.reader import get_investigation_subgraph

        graph_data = await get_investigation_subgraph(investigation_id)
    except Exception:
        pass

    # Build export
    return {
        "version": "1.0",
        "exported_at": datetime.now(UTC).isoformat(),
        "investigation": {
            "id": str(inv_row["id"]),
            "name": inv_row["name"],
            "target": inv_row["target"],
            "target_type": inv_row["target_type"],
            "status": inv_row["status"],
            "depth": inv_row["depth"],
            "api_calls_used": inv_row["api_calls_used"],
            "api_budget": inv_row["api_budget"],
            "entity_count": inv_row["entity_count"],
            "relationship_count": inv_row["relationship_count"],
            "observation_count": inv_row["observation_count"],
            "created_at": inv_row["created_at"].isoformat() if inv_row["created_at"] else "",
            "updated_at": inv_row["updated_at"].isoformat() if inv_row["updated_at"] else "",
        },
        "observations": [
            {
                "id": str(row["id"]),
                "source_adapter": row["source_adapter"],
                "source_version": row["source_version"],
                "collected_at": row["collected_at"].isoformat() if row["collected_at"] else "",
                "method": row["method"],
                "target": row["target"],
                "raw_response": json.loads(row["raw_response"])
                if isinstance(row["raw_response"], str)
                else row["raw_response"],
                "normalized_value": row["normalized_value"],
                "confidence": row["confidence"],
                "status": row["status"],
            }
            for row in obs_rows
        ],
        "entities": [
            {
                "id": row["id"],
                "type": row["type"],
                "value": row["value"],
                "confidence": row["confidence"],
                "first_seen": row["first_seen"].isoformat() if row["first_seen"] else None,
                "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
                "source_count": row["source_count"],
                "properties": json.loads(row["properties"])
                if isinstance(row["properties"], str)
                else row["properties"],
            }
            for row in entity_rows
        ],
        "activity_log": [
            {
                "event_type": row["event_type"],
                "details": json.loads(row["details"])
                if isinstance(row["details"], str)
                else row["details"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else "",
            }
            for row in activity_rows
        ],
        "graph": graph_data,
    }


async def import_investigation(data: dict) -> InvestigationResponse:
    """Import an investigation from exported JSON data.

    Creates a new investigation with the imported data. Generates new IDs
    to avoid conflicts with existing data.
    """
    from uuid import uuid4

    inv_data = data.get("investigation", {})
    new_id = str(uuid4())
    now = datetime.now(UTC)

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Create the investigation
        await conn.execute(
            """
            INSERT INTO investigations
                (id, name, target, target_type, status, depth, api_calls_used,
                 api_budget, entity_count, relationship_count, observation_count,
                 created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            new_id,
            inv_data.get("name", "Imported Investigation"),
            inv_data.get("target", ""),
            inv_data.get("target_type", "unknown"),
            "created",  # Always import as created, not the original status
            inv_data.get("depth", "standard"),
            0,  # Reset API calls
            inv_data.get("api_budget", 100),
            0,  # Will be updated after importing entities
            0,
            0,
            now,
            now,
        )

        # Import observations
        for obs in data.get("observations", []):
            obs_id = str(uuid4())
            raw_response = obs.get("raw_response", {})
            await conn.execute(
                """
                INSERT INTO observations
                    (id, investigation_id, source_adapter, source_version,
                     collected_at, method, target, raw_response, normalized_value,
                     confidence, status, error_message)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                obs_id,
                new_id,
                obs.get("source_adapter", ""),
                obs.get("source_version"),
                obs.get("collected_at", now),
                obs.get("method", ""),
                obs.get("target", ""),
                json.dumps(raw_response),
                obs.get("normalized_value"),
                obs.get("confidence"),
                obs.get("status", "success"),
                obs.get("error_message", ""),
            )

        # Import entities
        for entity in data.get("entities", []):
            entity_id = f"{entity.get('type', 'unknown').lower()}:{entity.get('value', '')}"
            # Use a new ID to avoid conflicts
            await conn.execute(
                """
                INSERT INTO entities
                    (id, investigation_id, type, value, confidence, first_seen,
                     last_seen, source_count, properties)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id, investigation_id) DO UPDATE SET
                    confidence = EXCLUDED.confidence,
                    last_seen = EXCLUDED.last_seen,
                    source_count = EXCLUDED.source_count
                """,
                entity_id,
                new_id,
                entity.get("type", "unknown"),
                entity.get("value", ""),
                entity.get("confidence", 0.0),
                entity.get("first_seen"),
                entity.get("last_seen"),
                entity.get("source_count", 1),
                json.dumps(entity.get("properties", {})),
            )

        # Import activity log
        for activity in data.get("activity_log", []):
            await conn.execute(
                """
                INSERT INTO activity_log (investigation_id, event_type, details, created_at)
                VALUES ($1, $2, $3, $4)
                """,
                new_id,
                activity.get("event_type", ""),
                json.dumps(activity.get("details", {})),
                activity.get("created_at", now),
            )

        # Update counts
        entity_count = len(data.get("entities", []))
        obs_count = len(data.get("observations", []))
        await conn.execute(
            """
            UPDATE investigations
            SET entity_count = $1, observation_count = $2
            WHERE id = $3
            """,
            entity_count,
            obs_count,
            new_id,
        )

    # Import graph data
    graph_data = data.get("graph", {})
    if graph_data.get("nodes") or graph_data.get("edges"):
        try:
            from app.graph.writer import write_graph
            from app.models.processing import ExtractedEntity, ExtractedRelationship

            # Convert graph nodes back to ExtractedEntity objects
            entities = []
            for node in graph_data.get("nodes", []):
                data_node = node.get("data", node)
                entity_id = data_node.get("id", "")
                if ":" in entity_id:
                    entity_type_str = entity_id.split(":", 1)[0]
                    value = entity_id.split(":", 1)[1]
                else:
                    entity_type_str = data_node.get("type", "unknown")
                    value = data_node.get("label", "")

                try:
                    entity_type = EntityType(entity_type_str)
                except ValueError:
                    entity_type = EntityType.DOMAIN

                entities.append(
                    ExtractedEntity(
                        id=entity_id,
                        entity_type=entity_type,
                        value=value,
                        confidence=data_node.get("confidence", 0.5),
                        first_seen=datetime.fromisoformat(data_node["first_seen"])
                        if data_node.get("first_seen")
                        else now,
                        last_seen=datetime.fromisoformat(data_node["last_seen"])
                        if data_node.get("last_seen")
                        else now,
                        source_count=data_node.get("source_count", 1),
                    )
                )

            # Convert graph edges back to ExtractedRelationship objects
            relationships = []
            for edge in graph_data.get("edges", []):
                data_edge = edge.get("data", edge)
                relationships.append(
                    ExtractedRelationship(
                        id=data_edge.get("id", str(uuid4())),
                        source_entity_id=data_edge.get("source", ""),
                        target_entity_id=data_edge.get("target", ""),
                        rel_type=RelationshipType(
                            data_edge.get("relationship_type", "co_occurs_with")
                        ),
                        confidence=data_edge.get("confidence", 0.5),
                        evidence_ids=data_edge.get("evidence", []),
                        discovered_at=datetime.fromisoformat(data_edge["discovered_at"])
                        if data_edge.get("discovered_at")
                        else now,
                        method=data_edge.get("method", "import"),
                    )
                )
            await write_graph(
                entities,
                relationships,
                investigation_id=new_id,
            )
        except Exception:
            pass  # Graph import is best-effort

    return await get_investigation(new_id)
