"""AI output validator — hallucination prevention and schema validation.

Task 6.13: Validate AI-referenced observation IDs exist in the database.
Ensure all AI output conforms to strict schemas before use.

Security: All AI output is untrusted. Validate every field. Never allow
LLM to reference arbitrary IDs, execute tools, or bypass deterministic controls.
"""

from __future__ import annotations

import logging
from typing import Any

from app.db.client import get_pool
from app.models.ai import AIAnalyzerOutput, AIPlannerOutput, PivotRecommendation

logger = logging.getLogger(__name__)


async def validate_observation_ids(
    observation_ids: list[str],
    investigation_id: str,
) -> list[str]:
    """Validate that observation IDs exist in the database for this investigation.

    Returns only the IDs that actually exist. Logs warnings for hallucinated IDs.

    Args:
        observation_ids: IDs referenced by the AI.
        investigation_id: Owning investigation UUID (isolation boundary).

    Returns:
        List of validated (existing) observation IDs.
    """
    if not observation_ids:
        return []

    # Filter out empty strings and ensure valid UUID format.
    import uuid

    valid_uuid_ids = []
    for oid in observation_ids:
        oid = oid.strip()
        if not oid:
            continue
        try:
            uuid.UUID(oid)
            valid_uuid_ids.append(oid)
        except ValueError:
            logger.warning("AI hallucinated non-UUID observation ID: %s", oid)

    if not valid_uuid_ids:
        return []

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text FROM observations
            WHERE id = ANY($1::uuid[])
              AND investigation_id = $2
            """,
            valid_uuid_ids,
            investigation_id,
        )

    valid_ids = {str(row["id"]) for row in rows}
    validated = [oid for oid in valid_uuid_ids if oid in valid_ids]

    # Include non-UUID strings in hallucinated set for logging
    clean_ids = [oid.strip() for oid in observation_ids if oid.strip()]
    hallucinated = set(clean_ids) - valid_ids
    if hallucinated:
        logger.warning(
            "AI referenced non-existent observation IDs (hallucination): %s",
            hallucinated,
        )

    return validated


async def validate_entity_ids(
    entity_ids: list[str],
    investigation_id: str,
) -> list[str]:
    """Validate that entity IDs exist in the graph for this investigation.

    Returns only the IDs that actually exist.

    Args:
        entity_ids: Entity IDs referenced by the AI.
        investigation_id: Owning investigation UUID.

    Returns:
        List of validated entity IDs.
    """
    if not entity_ids:
        return []

    clean_ids = [eid.strip() for eid in entity_ids if eid.strip()]
    if not clean_ids:
        return []

    try:
        from app.graph.client import get_driver

        driver = await get_driver()
        query = """
        MATCH (n)
        WHERE n.investigation_id = $investigation_id
          AND n.id IN $entity_ids
        RETURN n.id AS entity_id
        """
        async with driver.session() as session:
            result = await session.run(
                query, investigation_id=investigation_id, entity_ids=clean_ids
            )
            valid_ids = {record["entity_id"] async for record in result}
    except Exception:
        # If Neo4j is unavailable, fall back to PostgreSQL entities table.
        logger.debug("Neo4j unavailable for entity validation, falling back to PostgreSQL")
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id FROM entities
                WHERE id = ANY($1::text[])
                  AND investigation_id = $2
                """,
                clean_ids,
                investigation_id,
            )
        valid_ids = {row["id"] for row in rows}

    validated = [eid for eid in clean_ids if eid in valid_ids]
    hallucinated = set(clean_ids) - valid_ids
    if hallucinated:
        logger.warning(
            "AI referenced non-existent entity IDs (hallucination): %s",
            hallucinated,
        )

    return validated


def validate_planner_output(raw: dict[str, Any]) -> AIPlannerOutput | None:
    """Validate raw LLM JSON output against the AIPlannerOutput schema.

    Returns validated model or None if validation fails.
    Logs all validation errors.

    Args:
        raw: Raw JSON dict from the LLM.

    Returns:
        Validated AIPlannerOutput or None.
    """
    try:
        output = AIPlannerOutput.model_validate(raw)
        return output
    except Exception as exc:
        logger.warning("AI planner output validation failed: %s", exc)
        return None


def validate_analyzer_output(raw: dict[str, Any]) -> AIAnalyzerOutput | None:
    """Validate raw LLM JSON output against the AIAnalyzerOutput schema.

    Returns validated model or None if validation fails.

    Args:
        raw: Raw JSON dict from the LLM.

    Returns:
        Validated AIAnalyzerOutput or None.
    """
    try:
        output = AIAnalyzerOutput.model_validate(raw)
        return output
    except Exception as exc:
        logger.warning("AI analyzer output validation failed: %s", exc)
        return None


def sanitize_pivot_evidence_ids(
    pivots: list[PivotRecommendation],
    valid_obs_ids: set[str],
) -> list[PivotRecommendation]:
    """Remove invalid evidence_ids from pivot recommendations.

    Keeps only observation IDs that were validated against the database.

    Args:
        pivots: AI-generated pivot recommendations.
        valid_obs_ids: Set of validated observation IDs.

    Returns:
        Pivots with sanitized evidence_ids.
    """
    sanitized = []
    for pivot in pivots:
        pivot_copy = pivot.model_copy(
            update={"evidence_ids": [eid for eid in pivot.evidence_ids if eid in valid_obs_ids]}
        )
        sanitized.append(pivot_copy)
    return sanitized
