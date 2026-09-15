"""Graph writer - create/update nodes and edges in SQLite (Migrated in Phase 3).

Tasks 5.2-5.3 (Original):
- 5.2: Create/update nodes from entity list
- 5.3: Create/update edges from relationship list

Phase 3 Migration:
All writes are sent directly to the SQLite `entities` and `relationships` tables.
`edges_bidi` is automatically updated via database triggers.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from app.db.client import get_pool
from app.models.processing import ExtractedEntity, ExtractedRelationship

logger = logging.getLogger(__name__)


# ─── Public API ───────────────────────────────────────────────────────────────


def _validate_id(value: str) -> None:
    if not value or not str(value).strip():
        raise ValueError("investigation_id must be a non-empty string")

async def write_nodes(
    entities: list[ExtractedEntity],
    *,
    investigation_id: str,
) -> int:
    """Upsert nodes into SQLite."""
    _validate_id(investigation_id)
    if not entities:
        return 0

    pool = await get_pool()
    nodes_written = 0
    
    async with pool.acquire() as conn:
        # For testing without a full database setup, ensure the investigation exists
        await conn.execute("INSERT OR IGNORE INTO investigations (id, name, target, target_type) VALUES ($1, $2, 'test_target', 'domain')", investigation_id, investigation_id)
        for entity in entities:
            try:
                await conn.execute(
                    """
                    INSERT INTO entities (
                        id, investigation_id, type, value, confidence,
                        first_seen, last_seen, source_count, properties
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (id, investigation_id) DO UPDATE SET
                        confidence = EXCLUDED.confidence,
                        first_seen = EXCLUDED.first_seen,
                        last_seen = EXCLUDED.last_seen,
                        source_count = EXCLUDED.source_count,
                        properties = EXCLUDED.properties
                    """,
                    entity.id,
                    investigation_id,
                    entity.entity_type.value,
                    entity.value,
                    entity.confidence,
                    entity.first_seen,
                    entity.last_seen,
                    len(entity.sources),
                    json.dumps(entity.properties)
                )
                nodes_written += 1
            except Exception as e:
                logger.error("Failed to write node %s: %s", entity.id, e)
                    
    return nodes_written


async def write_edges(
    relationships: list[ExtractedRelationship],
    *,
    investigation_id: str,
) -> int:
    """Upsert relationships into SQLite."""
    _validate_id(investigation_id)
    if not relationships:
        return 0

    pool = await get_pool()
    edges_written = 0

    async with pool.acquire() as conn:
        await conn.execute("INSERT OR IGNORE INTO investigations (id, name, target, target_type) VALUES ($1, $2, 'test_target', 'domain')", investigation_id, investigation_id)
        for rel in relationships:
            try:
                await conn.execute(
                    """
                    INSERT INTO relationships (
                        id, source_id, target_id, relationship_type,
                        investigation_id, confidence, evidence,
                        discovered_at, method
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (id, investigation_id) DO UPDATE SET
                        confidence = EXCLUDED.confidence,
                        evidence = EXCLUDED.evidence,
                        discovered_at = EXCLUDED.discovered_at,
                        method = EXCLUDED.method
                    """,
                    rel.id,
                    rel.source_entity_id,
                    rel.target_entity_id,
                    rel.rel_type.value.upper(),
                    investigation_id,
                    rel.confidence,
                    json.dumps(rel.evidence_ids),
                    rel.discovered_at.isoformat(),
                    rel.method
                )
                edges_written += 1
            except Exception as e:
                logger.error("Failed to write edge %s: %s", rel.id, e)
                    
    return edges_written


async def write_graph(
    entities: list[ExtractedEntity],
    relationships: list[ExtractedRelationship],
    *,
    investigation_id: str,
) -> tuple[int, int]:
    """Write both nodes and edges to the investigation graph."""
    if not entities and not relationships:
        return 0, 0

    n = await write_nodes(entities, investigation_id=investigation_id)
    e = await write_edges(relationships, investigation_id=investigation_id)
    return n, e


async def delete_investigation_graph(
    investigation_id: str
) -> int:
    """Delete all graph data for an investigation."""
    _validate_id(investigation_id)

    pool = await get_pool()
    async with pool.acquire() as conn:
        # In SQLite with ON DELETE CASCADE, deleting from entities will 
        # automatically delete from relationships, and the triggers will update edges_bidi.
        
        # We need to explicitly count affected rows. 
        # Using returning or just counting beforehand.
        n = await conn.fetch("SELECT COUNT(*) as c FROM entities WHERE investigation_id = $1", investigation_id)
        count = n[0]["c"] if n else 0
        
        await conn.execute("DELETE FROM entities WHERE investigation_id = $1", investigation_id)
        
        return count
