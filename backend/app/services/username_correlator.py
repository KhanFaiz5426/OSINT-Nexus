"""Username correlation service — cross-platform identity correlation.

Cross-references username observations from multiple collectors to
identify accounts likely belonging to the same person. Uses shared
attributes (email, name, bio keywords, organization, website) to
compute a confidence score for each cross-platform match.

This service is deterministic — no LLM calls. All confidence scores
are computed from observable evidence only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.models import EntityType, RelationshipType
from app.models.processing import ExtractedEntity, ExtractedRelationship

logger = logging.getLogger(__name__)

# Attributes that, when shared, suggest the same person.
# Each attribute has a weight for confidence scoring.
SHARED_ATTRIBUTE_WEIGHTS: dict[str, float] = {
    "email": 0.95,
    "full_name": 0.85,
    "organization": 0.70,
    "website": 0.65,
    "bio_keywords": 0.55,
    "location": 0.50,
}

# Minimum confidence to create a cross-platform relationship.
MIN_CORRELATION_CONFIDENCE = 0.45


@dataclass
class PlatformAccount:
    """A discovered account on a specific platform."""

    platform: str
    username: str
    full_name: str = ""
    email: str = ""
    bio: str = ""
    organization: str = ""
    website: str = ""
    location: str = ""
    profile_url: str = ""
    observation_id: str = ""
    confidence: float = 0.0
    raw_data: dict[str, Any] = field(default_factory=dict)


def _normalize_text(text: str) -> str:
    """Lowercase and strip whitespace for comparison."""
    return text.strip().lower()


def _extract_bio_keywords(bio: str) -> set[str]:
    """Extract significant keywords from a bio string."""
    if not bio:
        return set()
    # Simple keyword extraction: split on whitespace, filter short words.
    words = {w.strip(".,;:!?()\"'-").lower() for w in bio.split()}
    return {w for w in words if len(w) > 3}


def _compute_shared_attributes(a: PlatformAccount, b: PlatformAccount) -> dict[str, bool]:
    """Determine which attributes are shared between two accounts."""
    shared: dict[str, bool] = {}

    # Email match (normalized).
    if a.email and b.email:
        shared["email"] = _normalize_text(a.email) == _normalize_text(b.email)

    # Full name match.
    if a.full_name and b.full_name:
        shared["full_name"] = _normalize_text(a.full_name) == _normalize_text(b.full_name)

    # Organization match.
    if a.organization and b.organization:
        shared["organization"] = _normalize_text(a.organization) == _normalize_text(b.organization)

    # Website match.
    if a.website and b.website:
        shared["website"] = _normalize_text(a.website) == _normalize_text(b.website)

    # Location match.
    if a.location and b.location:
        shared["location"] = _normalize_text(a.location) == _normalize_text(b.location)

    # Bio keyword overlap.
    a_keywords = _extract_bio_keywords(a.bio)
    b_keywords = _extract_bio_keywords(b.bio)
    if a_keywords and b_keywords:
        overlap = a_keywords & b_keywords
        # Require at least 2 keywords in common or 30% overlap.
        min_count = min(len(a_keywords), len(b_keywords))
        if min_count > 0:
            overlap_ratio = len(overlap) / min_count
            shared["bio_keywords"] = len(overlap) >= 2 or overlap_ratio >= 0.3
        else:
            shared["bio_keywords"] = False

    return shared


def _compute_correlation_confidence(
    shared: dict[str, bool],
    platform_count_a: int,
    platform_count_b: int,
) -> float:
    """Compute confidence score from shared attributes.

    Uses a weighted sum of matched attributes, with a small bonus
    for accounts that appear on many platforms (signal of real usage).
    """
    score = 0.0
    total_weight = 0.0

    for attr, weight in SHARED_ATTRIBUTE_WEIGHTS.items():
        total_weight += weight
        if shared.get(attr, False):
            score += weight

    if total_weight == 0:
        return 0.0

    # Normalize to 0-1 range.
    normalized = score / total_weight

    # Small bonus for multi-platform presence (diminishing returns).
    platform_bonus = min(0.1, 0.02 * max(platform_count_a, platform_count_b))
    normalized = min(1.0, normalized + platform_bonus)

    return round(normalized, 3)


def _extract_accounts_from_observations(
    observations: list[dict[str, Any]],
) -> list[PlatformAccount]:
    """Extract PlatformAccount objects from observation raw responses."""
    accounts: list[PlatformAccount] = []

    for obs in observations:
        source = obs.get("source_adapter", "")
        raw = obs.get("raw_response", {})
        obs_id = obs.get("id", "")

        profile = raw.get("profile", {})
        if not profile or not raw.get("found", False):
            continue

        # Map source_adapter to platform name.
        platform = source

        account = PlatformAccount(
            platform=platform,
            username=profile.get("name", "")
            or profile.get("username", "")
            or obs.get("target", ""),
            full_name=profile.get("full_name", "") or profile.get("name", "") or "",
            email=profile.get("email", "") or profile.get("public_email", "") or "",
            bio=profile.get("description", "")
            or profile.get("bio", "")
            or profile.get("about", "")
            or "",
            organization=profile.get("organization", "") or "",
            website=profile.get("website_url", "") or profile.get("website", "") or "",
            location=profile.get("location", "") or "",
            profile_url=profile.get("profile_url", "") or "",
            observation_id=obs_id,
            confidence=obs.get("confidence", 0.5),
            raw_data=raw,
        )
        accounts.append(account)

    return accounts


def correlate_username_accounts(
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Cross-reference username accounts across platforms.

    Takes all observations from a username investigation and identifies
    accounts likely belonging to the same person based on shared attributes.

    Args:
        observations: List of observation dicts from PostgreSQL.

    Returns:
        Dict with:
        - accounts: list of discovered platform accounts
        - correlations: list of cross-platform matches with confidence
        - entities: ExtractedEntity objects for graph storage
        - relationships: ExtractedRelationship objects for graph storage
    """
    accounts = _extract_accounts_from_observations(observations)

    if not accounts:
        return {
            "accounts": [],
            "correlations": [],
            "entities": [],
            "relationships": [],
        }

    # Group accounts by normalized username.
    username_groups: dict[str, list[PlatformAccount]] = {}
    for account in accounts:
        key = _normalize_text(account.username)
        username_groups.setdefault(key, []).append(account)

    correlations: list[dict[str, Any]] = []
    entities: list[ExtractedEntity] = []
    relationships: list[ExtractedRelationship] = []
    now = datetime.now(UTC)

    # For each group of accounts with the same username, check cross-platform matches.
    for username, group in username_groups.items():
        if len(group) < 2:
            # Single platform — just create entity.
            for account in group:
                entity_id = f"{EntityType.USERNAME.value.lower()}:{account.username}"
                entities.append(
                    ExtractedEntity(
                        id=entity_id,
                        entity_type=EntityType.USERNAME,
                        value=account.username,
                        confidence=account.confidence,
                        first_seen=now,
                        last_seen=now,
                        sources=[account.platform],
                        evidence_ids=[account.observation_id] if account.observation_id else [],
                    )
                )
            continue

        # Create USERNAME entity for the username itself.
        entity_id = f"{EntityType.USERNAME.value.lower()}:{username}"
        all_platforms = list({a.platform for a in group})
        all_evidence = [a.observation_id for a in group if a.observation_id]
        max_confidence = max(a.confidence for a in group)

        entities.append(
            ExtractedEntity(
                id=entity_id,
                entity_type=EntityType.USERNAME,
                value=username,
                confidence=max_confidence,
                first_seen=now,
                last_seen=now,
                sources=all_platforms,
                evidence_ids=all_evidence,
            )
        )

        # Create PERSON entity if we have a real name.
        for account in group:
            if account.full_name:
                person_id = (
                    f"{EntityType.PERSON.value.lower()}:{_normalize_text(account.full_name)}"
                )
                entities.append(
                    ExtractedEntity(
                        id=person_id,
                        entity_type=EntityType.PERSON,
                        value=account.full_name,
                        confidence=0.7,
                        first_seen=now,
                        last_seen=now,
                        sources=[account.platform],
                        evidence_ids=[account.observation_id] if account.observation_id else [],
                    )
                )
                # Link username → person.
                rel_id = f"username_person:{username}:{_normalize_text(account.full_name)}"
                relationships.append(
                    ExtractedRelationship(
                        id=rel_id,
                        source_entity_id=entity_id,
                        target_entity_id=person_id,
                        rel_type=RelationshipType.SAME_PERSON,
                        confidence=0.8,
                        discovered_at=now,
                        evidence_ids=[account.observation_id] if account.observation_id else [],
                    )
                )

        # Create EMAIL entities.
        for account in group:
            if account.email:
                norm_email = account.email.strip().lower()
                email_id = f"{EntityType.EMAIL.value.lower()}:{norm_email}"
                entities.append(
                    ExtractedEntity(
                        id=email_id,
                        entity_type=EntityType.EMAIL,
                        value=norm_email,
                        confidence=0.8,
                        first_seen=now,
                        last_seen=now,
                        sources=[account.platform],
                        evidence_ids=[account.observation_id] if account.observation_id else [],
                    )
                )
                # Link username → email.
                rel_id = f"username_email:{username}:{norm_email}"
                relationships.append(
                    ExtractedRelationship(
                        id=rel_id,
                        source_entity_id=entity_id,
                        target_entity_id=email_id,
                        rel_type=RelationshipType.HAS_EMAIL,
                        confidence=0.85,
                        discovered_at=now,
                        evidence_ids=[account.observation_id] if account.observation_id else [],
                    )
                )

        # Create ORGANIZATION entities.
        for account in group:
            if account.organization:
                org_val = _normalize_text(account.organization)
                org_id = f"{EntityType.ORGANIZATION.value.lower()}:{org_val}"
                entities.append(
                    ExtractedEntity(
                        id=org_id,
                        entity_type=EntityType.ORGANIZATION,
                        value=account.organization,
                        confidence=0.7,
                        first_seen=now,
                        last_seen=now,
                        sources=[account.platform],
                        evidence_ids=[account.observation_id] if account.observation_id else [],
                    )
                )

        # Cross-platform correlation: compare all pairs in the group.
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                shared = _compute_shared_attributes(a, b)
                has_shared = any(shared.values())

                if not has_shared:
                    # Same username on different platforms — still some signal.
                    confidence = 0.4
                    shared_summary = ["same_username"]
                else:
                    confidence = _compute_correlation_confidence(shared, len(group), len(group))
                    shared_summary = [k for k, v in shared.items() if v]

                if confidence >= MIN_CORRELATION_CONFIDENCE:
                    correlation = {
                        "platform_a": a.platform,
                        "platform_b": b.platform,
                        "username_a": a.username,
                        "username_b": b.username,
                        "confidence": confidence,
                        "shared_attributes": shared_summary,
                    }
                    correlations.append(correlation)

                    # Create cross-platform relationship.
                    rel_id = f"cross_platform:{a.platform}:{b.platform}:{username}"
                    relationships.append(
                        ExtractedRelationship(
                            id=rel_id,
                            source_entity_id=f"{EntityType.USERNAME.value.lower()}:{a.username}",
                            target_entity_id=f"{EntityType.USERNAME.value.lower()}:{b.username}",
                            rel_type=RelationshipType.SAME_PERSON,
                            confidence=confidence,
                            discovered_at=now,
                            evidence_ids=[
                                eid for eid in [a.observation_id, b.observation_id] if eid
                            ],
                        )
                    )

    # Deduplicate entities and relationships.
    entities = _deduplicate_entities(entities)
    relationships = _deduplicate_relationships(relationships)

    logger.info(
        "Username correlation: %d accounts → %d entities, %d correlations, %d relationships",
        len(accounts),
        len(entities),
        len(correlations),
        len(relationships),
    )

    return {
        "accounts": [{"platform": a.platform, "username": a.username} for a in accounts],
        "correlations": correlations,
        "entities": entities,
        "relationships": relationships,
    }


def _deduplicate_entities(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
    """Deduplicate entities by ID, merging sources and evidence."""
    seen: dict[str, ExtractedEntity] = {}
    for entity in entities:
        if entity.id in seen:
            existing = seen[entity.id]
            for src in entity.sources:
                if src not in existing.sources:
                    existing.sources.append(src)
            for eid in entity.evidence_ids:
                if eid not in existing.evidence_ids:
                    existing.evidence_ids.append(eid)
            if entity.confidence > existing.confidence:
                existing.confidence = entity.confidence
        else:
            seen[entity.id] = entity
    return list(seen.values())


def _deduplicate_relationships(
    relationships: list[ExtractedRelationship],
) -> list[ExtractedRelationship]:
    """Deduplicate relationships by ID, merging sources and evidence."""
    seen: dict[str, ExtractedRelationship] = {}
    for rel in relationships:
        if rel.id in seen:
            existing = seen[rel.id]
            for eid in rel.evidence_ids:
                if eid not in existing.evidence_ids:
                    existing.evidence_ids.append(eid)
            if rel.confidence > existing.confidence:
                existing.confidence = rel.confidence
        else:
            seen[rel.id] = rel
    return list(seen.values())
