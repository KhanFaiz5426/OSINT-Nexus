"""Confidence scorer — computes confidence scores for entities and relationships.

Task 4.13: source_reliability × data_quality × corroboration × recency

Formula:
    confidence = min(1.0, source_reliability × data_quality × corroboration_bonus × recency_factor)

Ranges:
    source_reliability: 0.60–0.95 (based on source type)
    data_quality: 0.7–1.0 (exact match=1.0, inferred=0.7)
    corroboration: 1.0–1.2 (bonus for multiple independent sources)
    recency: 0.7–1.0 (decay based on age of observation)
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.processing import ExtractedEntity, ExtractedRelationship

# ── Source reliability scores ─────────────────────────────────────────────────

SOURCE_RELIABILITY: dict[str, float] = {
    "dns": 0.95,
    "whois": 0.90,
    "certificate_transparency": 0.92,
    "ip_to_asn": 0.88,
    "http": 0.85,
    "github": 0.82,
    "threat_intel": 0.80,
    "search": 0.70,
}

DEFAULT_SOURCE_RELIABILITY = 0.75


# ── Public API ────────────────────────────────────────────────────────────────


def score_entity(
    entity: ExtractedEntity,
    *,
    reference_time: datetime | None = None,
    source_overrides: dict[str, float] | None = None,
) -> float:
    """Compute confidence score for an entity (Task 4.13).

    Args:
        entity: The entity to score.
        reference_time: Current time for recency calculation (defaults to now).
        source_overrides: Custom source reliability scores.

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    now = reference_time or datetime.now(UTC)

    # Source reliability: average across sources
    reliability = _compute_source_reliability(entity.sources, source_overrides)

    # Data quality: based on entity properties
    quality = _compute_data_quality(entity)

    # Corroboration: bonus for multiple independent sources
    corroboration = _compute_corroboration_bonus(entity.sources)

    # Recency: decay based on age of last_seen
    recency = _compute_recency_factor(entity.last_seen, now)

    raw_score = reliability * quality * corroboration * recency
    return max(0.0, min(1.0, raw_score))


def score_relationship(
    relationship: ExtractedRelationship,
    entities: dict[str, ExtractedEntity] | None = None,
    *,
    reference_time: datetime | None = None,
    source_overrides: dict[str, float] | None = None,
) -> float:
    """Compute confidence score for a relationship (Task 4.13).

    The relationship confidence is influenced by:
    1. Source reliability (from the relationship's evidence sources)
    2. Method reliability (how the relationship was detected)
    3. Entity confidence (if entities are provided)
    4. Corroboration (multiple evidence sources)
    5. Recency

    Args:
        relationship: The relationship to score.
        entities: Optional entity lookup for entity-confidence boost.
        reference_time: Current time for recency calculation.
        source_overrides: Custom source reliability scores.

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    now = reference_time or datetime.now(UTC)

    # Method reliability (structural detections are more reliable)
    method_reliability = _method_reliability(relationship.method)

    # Corroboration from evidence
    corroboration = _compute_corroboration_bonus(relationship.evidence_ids)

    # Entity confidence boost
    entity_boost = 1.0
    if entities:
        src_entity = entities.get(relationship.source_entity_id)
        tgt_entity = entities.get(relationship.target_entity_id)
        if src_entity and tgt_entity:
            avg_conf = (src_entity.confidence + tgt_entity.confidence) / 2
            entity_boost = 0.8 + (avg_conf * 0.2)  # 0.8–1.0 range

    # Recency
    recency = _compute_recency_factor(relationship.discovered_at, now)

    raw_score = method_reliability * corroboration * entity_boost * recency
    return max(0.0, min(1.0, raw_score))


def score_all(
    entities: list[ExtractedEntity],
    relationships: list[ExtractedRelationship],
    *,
    reference_time: datetime | None = None,
    source_overrides: dict[str, float] | None = None,
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Score and update confidence for all entities and relationships.

    Returns updated copies with recalculated confidence scores.
    """
    now = reference_time or datetime.now(UTC)
    {e.id: e for e in entities}

    scored_entities = []
    for entity in entities:
        scored = entity.model_copy(deep=True)
        scored.confidence = score_entity(
            scored,
            reference_time=now,
            source_overrides=source_overrides,
        )
        scored_entities.append(scored)

    scored_rels = []
    entity_lookup_scored = {e.id: e for e in scored_entities}
    for rel in relationships:
        scored = rel.model_copy(deep=True)
        scored.confidence = score_relationship(
            scored,
            entities=entity_lookup_scored,
            reference_time=now,
            source_overrides=source_overrides,
        )
        scored_rels.append(scored)

    return scored_entities, scored_rels


# ── Internal helpers ──────────────────────────────────────────────────────────


def _compute_source_reliability(
    sources: list[str],
    overrides: dict[str, float] | None = None,
) -> float:
    """Average source reliability across all contributing sources."""
    if not sources:
        return DEFAULT_SOURCE_RELIABILITY

    scores = []
    for src in sources:
        if overrides and src in overrides:
            scores.append(overrides[src])
        else:
            scores.append(SOURCE_RELIABILITY.get(src, DEFAULT_SOURCE_RELIABILITY))

    return sum(scores) / len(scores) if scores else DEFAULT_SOURCE_RELIABILITY


def _compute_data_quality(entity: ExtractedEntity) -> float:
    """Estimate data quality based on entity completeness.

    Higher quality if:
    - Has multiple sources (cross-confirmed)
    - Has evidence IDs (traceable)
    - Has meaningful properties
    """
    quality = 0.7  # base

    # Multiple sources boost
    if len(entity.sources) >= 3:
        quality += 0.15
    elif len(entity.sources) >= 2:
        quality += 0.10
    elif len(entity.sources) >= 1:
        quality += 0.05

    # Evidence traceability
    if len(entity.evidence_ids) >= 2:
        quality += 0.10
    elif len(entity.evidence_ids) >= 1:
        quality += 0.05

    # Properties completeness
    if entity.properties:
        quality += min(0.05, len(entity.properties) * 0.01)

    return min(1.0, quality)


def _compute_corroboration_bonus(sources: list[str]) -> float:
    """Bonus for multiple independent sources confirming the same fact.

    1 source → 1.0 (no bonus)
    2 sources → 1.05
    3+ sources → 1.10 (max bonus 1.2)
    """
    unique_sources = len(set(sources))
    if unique_sources >= 3:
        return 1.15
    if unique_sources == 2:
        return 1.08
    return 1.0


def _compute_recency_factor(
    last_seen: datetime | None,
    reference_time: datetime,
) -> float:
    """Recency decay: newer observations score higher.

    0-7 days → 1.0
    7-30 days → 0.95
    30-90 days → 0.90
    90-180 days → 0.85
    180-365 days → 0.80
    >365 days → 0.75 (minimum)
    """
    if last_seen is None:
        return 0.85

    age = reference_time - last_seen
    days = age.total_seconds() / 86400

    if days <= 7:
        return 1.0
    if days <= 30:
        return 0.95
    if days <= 90:
        return 0.90
    if days <= 180:
        return 0.85
    if days <= 365:
        return 0.80
    return 0.75


def _method_reliability(method: str) -> float:
    """Reliability score based on how the relationship was detected.

    Direct structural detections (DNS records, WHOIS data) are more reliable
    than inferred detections (co-occurrence, pattern matching).
    """
    reliability_map: dict[str, float] = {
        "dns_a_record": 0.95,
        "dns_aaaa_record": 0.95,
        "dns_mx_record": 0.90,
        "dns_ns_record": 0.95,
        "dns_soa_mname": 0.90,
        "dns_soa_rname": 0.70,
        "dns_ptr_record": 0.85,
        "whois_registrant_email": 0.80,
        "whois_registrant_name": 0.70,
        "whois_registrar": 0.85,
        "whois_nameserver": 0.90,
        "ct_certificate": 0.92,
        "ct_issuer": 0.88,
        "ct_san": 0.90,
        "ip_to_asn": 0.88,
        "http_tech_detection": 0.85,
        "http_redirect": 0.80,
        "threat_intel_abuseipdb": 0.80,
        "threat_intel_urlhaus": 0.78,
        "github_profile": 0.82,
        "github_repos": 0.85,
        "co_occurrence": 0.65,
    }
    return reliability_map.get(method, 0.75)
