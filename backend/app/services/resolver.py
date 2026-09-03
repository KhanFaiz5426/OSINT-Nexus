"""Entity resolver — deduplicates and resolves entities across sources.

Tasks 4.9–4.11:
- 4.9: Exact match deduplication
- 4.10: Normalized match deduplication
- 4.11: Co-occurrence detection (entities appearing together)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.models import EntityType, RelationshipType
from app.models.processing import ExtractedEntity, ExtractedRelationship

# ── Exact match resolution (Task 4.9) ────────────────────────────────────────


def resolve_exact(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
    """Deduplicate entities by exact ID match (Task 4.9).

    Entities with the same `id` (e.g., 'domain:example.com') are merged.
    Merged entities inherit all sources and evidence_ids.
    The merged entity retains the highest confidence score.

    Args:
        entities: List of extracted entities (may contain duplicates).

    Returns:
        Deduplicated list of entities.
    """
    merged: dict[str, ExtractedEntity] = {}

    for entity in entities:
        key = entity.id
        if key in merged:
            existing = merged[key]
            # Merge sources
            for src in entity.sources:
                if src not in existing.sources:
                    existing.sources.append(src)
            # Merge evidence
            for eid in entity.evidence_ids:
                if eid not in existing.evidence_ids:
                    existing.evidence_ids.append(eid)
            # Keep highest confidence
            if entity.confidence > existing.confidence:
                existing.confidence = entity.confidence
            # Update timestamps
            if entity.first_seen < existing.first_seen:
                existing.first_seen = entity.first_seen
            if entity.last_seen > existing.last_seen:
                existing.last_seen = entity.last_seen
            # Merge properties
            for k, v in entity.properties.items():
                if k not in existing.properties:
                    existing.properties[k] = v
        else:
            merged[key] = entity.model_copy(deep=True)

    return list(merged.values())


# ── Normalized match resolution (Task 4.10) ──────────────────────────────────


def resolve_normalized(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
    """Deduplicate entities by normalized value within each type (Task 4.10).

    After exact-match resolution, some entities may have different IDs
    but the same normalized value (e.g., from different collector formats).
    This function merges them.

    Args:
        entities: List of entities (already exact-resolved preferred).

    Returns:
        Further deduplicated list.
    """
    # Group by entity type
    by_type: dict[EntityType, list[ExtractedEntity]] = defaultdict(list)
    for entity in entities:
        by_type[entity.entity_type].append(entity)

    resolved: list[ExtractedEntity] = []

    for _etype, type_entities in by_type.items():
        # Group by normalized value
        by_value: dict[str, list[ExtractedEntity]] = defaultdict(list)
        for entity in type_entities:
            by_value[entity.value].append(entity)

        for _norm_value, value_entities in by_value.items():
            if len(value_entities) == 1:
                resolved.append(value_entities[0])
            else:
                # Merge all entities with the same value
                merged = _merge_entity_group(value_entities)
                resolved.append(merged)

    return resolved


def _merge_entity_group(entities: list[ExtractedEntity]) -> ExtractedEntity:
    """Merge a group of entities that share the same normalized value."""
    if len(entities) == 1:
        return entities[0]

    # Sort by confidence descending; use the best as base
    entities_sorted = sorted(entities, key=lambda e: e.confidence, reverse=True)
    base = entities_sorted[0].model_copy(deep=True)

    for other in entities_sorted[1:]:
        # Merge sources
        for src in other.sources:
            if src not in base.sources:
                base.sources.append(src)
        # Merge evidence
        for eid in other.evidence_ids:
            if eid not in base.evidence_ids:
                base.evidence_ids.append(eid)
        # Keep best confidence (already from base)
        # Update timestamps
        if other.first_seen < base.first_seen:
            base.first_seen = other.first_seen
        if other.last_seen > base.last_seen:
            base.last_seen = other.last_seen
        # Merge properties (base wins on conflicts)
        for k, v in other.properties.items():
            if k not in base.properties:
                base.properties[k] = v

    return base


# ── Co-occurrence detection (Task 4.11) ──────────────────────────────────────


def detect_co_occurrences(
    entities: list[ExtractedEntity],
    observations: list[dict[str, Any]],
) -> list[ExtractedRelationship]:
    """Detect entities that co-occur in the same observations (Task 4.11).

    When multiple entities share the same observation_id, they are
    linked by co-occurrence relationships. This helps discover connections
    that are not directly structural (e.g., two domains appearing in
    the same WHOIS record).

    Args:
        entities: Resolved entity list.
        observations: List of observation dicts, each with an 'id' field
                      and an 'entities' list of entity IDs.

    Returns:
        List of co-occurrence relationships.
    """
    # Build observation → entity IDs mapping
    obs_entities: dict[str, set[str]] = defaultdict(set)
    for obs in observations:
        obs_id = obs.get("id", "")
        if not obs_id:
            continue
        for eid in obs.get("entities", []):
            obs_entities[obs_id].add(eid)

    # Build entity → observations mapping
    entity_obs: dict[str, set[str]] = defaultdict(set)
    for obs_id, eids in obs_entities.items():
        for eid in eids:
            entity_obs[eid].add(obs_id)

    # Find co-occurring entity pairs
    relationships: list[ExtractedRelationship] = []
    seen_pairs: set[tuple[str, str]] = set()
    now = datetime.now(UTC)

    # Build entity lookup
    entity_lookup = {e.id: e for e in entities}

    for obs_id, eids in obs_entities.items():
        eid_list = sorted(eids)
        for i in range(len(eid_list)):
            for j in range(i + 1, len(eid_list)):
                eid_a, eid_b = eid_list[i], eid_list[j]
                pair = (eid_a, eid_b)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                # Both entities must exist in our entity list
                if eid_a not in entity_lookup or eid_b not in entity_lookup:
                    continue

                # Calculate co-occurrence confidence based on shared observations
                shared_obs = entity_obs[eid_a] & entity_obs[eid_b]
                total_obs_a = len(entity_obs[eid_a])
                total_obs_b = len(entity_obs[eid_b])

                if total_obs_a == 0 or total_obs_b == 0:
                    continue

                # Jaccard-like coefficient
                union = len(entity_obs[eid_a] | entity_obs[eid_b])
                confidence = min(0.9, len(shared_obs) / union * 1.5) if union > 0 else 0.0
                confidence = max(0.3, min(confidence, 0.9))

                rel_id = f"{eid_a}:co_occurs_with:{eid_b}"
                relationships.append(
                    ExtractedRelationship(
                        id=rel_id,
                        source_entity_id=eid_a,
                        target_entity_id=eid_b,
                        rel_type=RelationshipType.CO_OCCURS_WITH,
                        confidence=confidence,
                        evidence_ids=[obs_id],
                        discovered_at=now,
                        method="co_occurrence",
                    )
                )

    return relationships


# ── Full resolution pipeline ─────────────────────────────────────────────────


def resolve_entities(
    entities: list[ExtractedEntity],
    observations: list[dict[str, Any]] | None = None,
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Run the full entity resolution pipeline.

    1. Exact match deduplication
    2. Normalized match deduplication
    3. Co-occurrence detection (if observations provided)

    Args:
        entities: Raw extracted entities.
        observations: Optional observation data for co-occurrence.

    Returns:
        (resolved_entities, co_occurrence_relationships)
    """
    # Step 1: Exact match
    resolved = resolve_exact(entities)

    # Step 2: Normalized match
    resolved = resolve_normalized(resolved)

    # Step 3: Co-occurrence
    co_occur_rels: list[ExtractedRelationship] = []
    if observations:
        co_occur_rels = detect_co_occurrences(resolved, observations)

    return resolved, co_occur_rels
