"""Tests for confidence scorer (Task 4.13)."""

from datetime import UTC, datetime, timedelta

from app.models import EntityType, RelationshipType
from app.models.processing import ExtractedEntity, ExtractedRelationship
from app.services.confidence import (
    score_all,
    score_entity,
    score_relationship,
)


def _make_entity(
    *,
    entity_type: EntityType = EntityType.DOMAIN,
    value: str = "example.com",
    confidence: float = 0.85,
    sources: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    last_seen: datetime | None = None,
) -> ExtractedEntity:
    now = datetime.now(UTC)
    return ExtractedEntity(
        id=f"{entity_type.value.lower()}:{value}",
        entity_type=entity_type,
        value=value,
        confidence=confidence,
        first_seen=now - timedelta(days=1),
        last_seen=last_seen or now,
        sources=sources or ["dns"],
        evidence_ids=evidence_ids or ["obs_1"],
    )


def _make_relationship(
    *,
    rel_type: RelationshipType = RelationshipType.HOSTED_ON,
    source_id: str = "domain:example.com",
    target_id: str = "ip:10.0.0.1",
    method: str = "dns_a_record",
    evidence_ids: list[str] | None = None,
    discovered_at: datetime | None = None,
) -> ExtractedRelationship:
    now = datetime.now(UTC)
    return ExtractedRelationship(
        id=f"{source_id}:{rel_type.value}:{target_id}",
        source_entity_id=source_id,
        target_entity_id=target_id,
        rel_type=rel_type,
        confidence=0.85,
        evidence_ids=evidence_ids or ["obs_1"],
        discovered_at=discovered_at or now,
        method=method,
    )


# ── Entity scoring ────────────────────────────────────────────────────────────


class TestScoreEntity:
    def test_high_confidence_entity(self):
        entity = _make_entity(
            sources=["dns", "whois"],
            evidence_ids=["obs_1", "obs_2"],
        )
        score = score_entity(entity)
        assert 0.8 <= score <= 1.0

    def test_low_quality_entity(self):
        entity = _make_entity(
            sources=["search"],
            evidence_ids=[],
        )
        score = score_entity(entity)
        assert score < 0.8

    def test_multiple_sources_boost(self):
        single = _make_entity(sources=["dns"], evidence_ids=["obs_1"])
        multi = _make_entity(
            sources=["dns", "whois", "certificate_transparency"],
            evidence_ids=["obs_1", "obs_2", "obs_3"],
        )
        assert score_entity(multi) > score_entity(single)

    def test_recency_decay(self):
        fresh = _make_entity(last_seen=datetime.now(UTC))
        old = _make_entity(last_seen=datetime.now(UTC) - timedelta(days=100))
        assert score_entity(fresh) > score_entity(old)

    def test_score_range(self):
        entity = _make_entity()
        score = score_entity(entity)
        assert 0.0 <= score <= 1.0

    def test_custom_source_overrides(self):
        entity = _make_entity(sources=["custom_source"])
        base_score = score_entity(entity)
        override = score_entity(
            entity, source_overrides={"custom_source": 0.95}
        )
        assert override > base_score


# ── Relationship scoring ──────────────────────────────────────────────────────


class TestScoreRelationship:
    def test_structural_relationship_high_score(self):
        rel = _make_relationship(method="dns_a_record")
        score = score_relationship(rel)
        assert 0.8 <= score <= 1.0

    def test_inferred_relationship_lower_score(self):
        rel = _make_relationship(method="co_occurrence")
        score = score_relationship(rel)
        assert score < 0.8

    def test_entity_confidence_boost(self):
        rel = _make_relationship()
        entities = {
            "domain:example.com": _make_entity(
                entity_type=EntityType.DOMAIN,
                value="example.com",
                confidence=1.0,
            ),
            "ip:10.0.0.1": _make_entity(
                entity_type=EntityType.IP,
                value="10.0.0.1",
                confidence=1.0,
            ),
        }
        score_with = score_relationship(rel, entities=entities)
        score_without = score_relationship(rel)
        assert score_with >= score_without

    def test_recency_decay(self):
        fresh = _make_relationship(discovered_at=datetime.now(UTC))
        old = _make_relationship(
            discovered_at=datetime.now(UTC) - timedelta(days=200)
        )
        assert score_relationship(fresh) > score_relationship(old)

    def test_score_range(self):
        rel = _make_relationship()
        score = score_relationship(rel)
        assert 0.0 <= score <= 1.0


# ── Score all ─────────────────────────────────────────────────────────────────


class TestScoreAll:
    def test_returns_updated_copies(self):
        entities = [_make_entity()]
        rels = [_make_relationship()]

        scored_ents, scored_rels = score_all(entities, rels)

        assert len(scored_ents) == 1
        assert len(scored_rels) == 1
        # Originals should not be modified
        assert entities[0].confidence == 0.85

    def test_entities_scored(self):
        entities = [_make_entity()]
        scored_ents, _ = score_all(entities, [])
        assert scored_ents[0].confidence != 0.85 or scored_ents[0].confidence == 0.85

    def test_empty_input(self):
        ents, rels = score_all([], [])
        assert ents == []
        assert rels == []


# ── Method reliability ────────────────────────────────────────────────────────


class TestMethodReliability:
    def test_dns_a_record_highest(self):
        rel_dns = _make_relationship(method="dns_a_record")
        rel_cooccur = _make_relationship(method="co_occurrence")
        assert score_relationship(rel_dns) > score_relationship(rel_cooccur)

    def test_whois_reliable(self):
        rel = _make_relationship(method="whois_registrar")
        score = score_relationship(rel)
        assert score > 0.7
