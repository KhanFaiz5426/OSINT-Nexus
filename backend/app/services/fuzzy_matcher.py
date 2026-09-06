"""Fuzzy matcher — string similarity for entity deduplication.

Uses stdlib difflib.SequenceMatcher for Levenshtein-like similarity scoring.
No external dependencies required.
"""

from __future__ import annotations

import logging
from difflib import SequenceMatcher

from app.models import EntityType
from app.models.processing import ExtractedEntity, ExtractedRelationship

logger = logging.getLogger(__name__)

# Similarity threshold for considering two entities as potential duplicates
SIMILARITY_THRESHOLD = 0.85

# Entity types that benefit from fuzzy matching
FUZZY_MATCHABLE_TYPES = {
    EntityType.ORGANIZATION,
    EntityType.PERSON,
    EntityType.USERNAME,
}


def string_similarity(a: str, b: str) -> float:
    """Compute similarity ratio between two strings.

    Uses SequenceMatcher which provides a ratio similar to Levenshtein
    but based on the longest common subsequence.

    Args:
        a: First string.
        b: Second string.

    Returns:
        Similarity ratio between 0.0 and 1.0.
    """
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_similar_entities(
    entities: list[ExtractedEntity],
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[tuple[ExtractedEntity, ExtractedEntity, float]]:
    """Find pairs of entities that are likely duplicates.

    Compares entities of the same type using string similarity on their values.

    Args:
        entities: List of extracted entities to compare.
        threshold: Minimum similarity ratio to consider as potential duplicates.

    Returns:
        List of (entity_a, entity_b, similarity_score) tuples.
    """
    similar_pairs: list[tuple[ExtractedEntity, ExtractedEntity, float]] = []

    # Group entities by type for comparison
    by_type: dict[EntityType, list[ExtractedEntity]] = {}
    for entity in entities:
        if entity.entity_type in FUZZY_MATCHABLE_TYPES:
            by_type.setdefault(entity.entity_type, []).append(entity)

    # Compare entities within each type
    for entity_type, type_entities in by_type.items():
        for i in range(len(type_entities)):
            for j in range(i + 1, len(type_entities)):
                entity_a = type_entities[i]
                entity_b = type_entities[j]

                # Skip if same ID (exact duplicates handled elsewhere)
                if entity_a.id == entity_b.id:
                    continue

                # Compute similarity
                similarity = string_similarity(entity_a.value, entity_b.value)

                if similarity >= threshold:
                    similar_pairs.append((entity_a, entity_b, similarity))
                    logger.debug(
                        "Similar entities found: %s ~= %s (score: %.2f)",
                        entity_a.value,
                        entity_b.value,
                        similarity,
                    )

    return similar_pairs


def create_similarity_relationships(
    similar_pairs: list[tuple[ExtractedEntity, ExtractedEntity, float]],
    method: str = "fuzzy_similarity",
) -> list[ExtractedRelationship]:
    """Create CO_OCCURS_WITH relationships for similar entity pairs.

    Args:
        similar_pairs: Pairs of similar entities from find_similar_entities.
        method: Method string for the relationship.

    Returns:
        List of relationships linking similar entities.
    """
    from datetime import UTC, datetime
    from uuid import uuid4

    relationships: list[ExtractedRelationship] = []
    now = datetime.now(UTC)

    for entity_a, entity_b, similarity in similar_pairs:
        # Create a deterministic ID based on the entity pair
        sorted_ids = sorted([entity_a.id, entity_b.id])
        rel_id = f"similarity:{sorted_ids[0]}:{sorted_ids[1]}"

        relationships.append(
            ExtractedRelationship(
                id=rel_id,
                source_entity_id=entity_a.id,
                target_entity_id=entity_b.id,
                rel_type="co_occurs_with",
                confidence=similarity,
                evidence_ids=[],
                discovered_at=now,
                method=method,
                properties={"similarity_score": similarity},
            )
        )

    return relationships


def normalize_for_comparison(value: str, entity_type: EntityType) -> str:
    """Normalize a value for better fuzzy comparison.

    Applies type-specific normalization before similarity comparison.
    """
    normalized = value.lower().strip()

    if entity_type == EntityType.ORGANIZATION:
        # Remove common suffixes
        for suffix in [" inc", " llc", " ltd", " corp", " co", " company", " corporation"]:
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)].strip()
        # Remove punctuation
        normalized = normalized.replace(".", "").replace(",", "").replace("'", "")

    elif entity_type == EntityType.USERNAME:
        # Remove common username prefixes/suffixes
        normalized = normalized.replace("_", "").replace("-", "").replace(".", "")

    elif entity_type == EntityType.EMAIL:
        # For emails, focus on the local part
        if "@" in normalized:
            normalized = normalized.split("@")[0]

    return normalized
