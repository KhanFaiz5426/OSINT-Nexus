"""Tests for entity resolver (Tasks 4.9–4.11)."""


from app.models import EntityType, RelationshipType
from app.models.processing import ExtractedEntity
from app.services.resolver import (
    detect_co_occurrences,
    resolve_entities,
    resolve_exact,
    resolve_normalized,
)


def _make_entity(
    entity_type: EntityType,
    value: str,
    *,
    sources: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    confidence: float = 0.85,
) -> ExtractedEntity:
    """Helper to create an entity with sensible defaults."""
    return ExtractedEntity(
        id=f"{entity_type.value.lower()}:{value}",
        entity_type=entity_type,
        value=value,
        confidence=confidence,
        sources=sources or ["dns"],
        evidence_ids=evidence_ids or ["obs_1"],
    )


# ── Task 4.9: Exact match deduplication ──────────────────────────────────────


class TestResolveExact:
    def test_merge_identical_entities(self):
        e1 = _make_entity(EntityType.IP, "10.0.0.1", sources=["dns"], evidence_ids=["obs_1"])
        e2 = _make_entity(EntityType.IP, "10.0.0.1", sources=["whois"], evidence_ids=["obs_2"])

        resolved = resolve_exact([e1, e2])
        assert len(resolved) == 1
        assert resolved[0].sources == ["dns", "whois"]
        assert resolved[0].evidence_ids == ["obs_1", "obs_2"]

    def test_no_merge_different_values(self):
        e1 = _make_entity(EntityType.IP, "10.0.0.1")
        e2 = _make_entity(EntityType.IP, "10.0.0.2")

        resolved = resolve_exact([e1, e2])
        assert len(resolved) == 2

    def test_no_merge_different_types(self):
        e1 = _make_entity(EntityType.IP, "10.0.0.1")
        e2 = _make_entity(EntityType.DOMAIN, "10.0.0.1")

        resolved = resolve_exact([e1, e2])
        assert len(resolved) == 2

    def test_keep_highest_confidence(self):
        e1 = _make_entity(EntityType.IP, "10.0.0.1", confidence=0.7)
        e2 = _make_entity(EntityType.IP, "10.0.0.1", confidence=0.9)

        resolved = resolve_exact([e1, e2])
        assert len(resolved) == 1
        assert resolved[0].confidence == 0.9

    def test_empty_input(self):
        assert resolve_exact([]) == []


# ── Task 4.10: Normalized match deduplication ─────────────────────────────────


class TestResolveNormalized:
    def test_merge_same_value_different_ids(self):
        # Two entities with same value but possibly different ID formats
        e1 = _make_entity(EntityType.IP, "10.0.0.1")
        e2 = _make_entity(EntityType.IP, "10.0.0.1")

        resolved = resolve_normalized([e1, e2])
        assert len(resolved) == 1

    def test_no_merge_different_values(self):
        e1 = _make_entity(EntityType.IP, "10.0.0.1")
        e2 = _make_entity(EntityType.IP, "10.0.0.2")

        resolved = resolve_normalized([e1, e2])
        assert len(resolved) == 2

    def test_merge_across_different_sources(self):
        e1 = _make_entity(
            EntityType.DOMAIN, "example.com",
            sources=["dns"], evidence_ids=["obs_1"],
        )
        e2 = _make_entity(
            EntityType.DOMAIN, "example.com",
            sources=["whois"], evidence_ids=["obs_2"],
        )

        resolved = resolve_normalized([e1, e2])
        assert len(resolved) == 1
        assert "dns" in resolved[0].sources
        assert "whois" in resolved[0].sources

    def test_different_types_not_merged(self):
        e1 = _make_entity(EntityType.DOMAIN, "example.com")
        e2 = _make_entity(EntityType.SUBDOMAIN, "example.com")

        resolved = resolve_normalized([e1, e2])
        assert len(resolved) == 2


# ── Task 4.11: Co-occurrence detection ────────────────────────────────────────


class TestDetectCoOccurrences:
    def test_co_occurrence_same_observation(self):
        e1 = _make_entity(EntityType.DOMAIN, "example.com")
        e2 = _make_entity(EntityType.IP, "10.0.0.1")

        observations = [
            {"id": "obs_1", "entities": ["domain:example.com", "ip:10.0.0.1"]},
        ]

        rels = detect_co_occurrences([e1, e2], observations)
        assert len(rels) == 1
        assert rels[0].rel_type == RelationshipType.CO_OCCURS_WITH

    def test_no_co_occurrence_different_observations(self):
        e1 = _make_entity(EntityType.DOMAIN, "example.com")
        e2 = _make_entity(EntityType.IP, "10.0.0.1")

        observations = [
            {"id": "obs_1", "entities": ["domain:example.com"]},
            {"id": "obs_2", "entities": ["ip:10.0.0.1"]},
        ]

        rels = detect_co_occurrences([e1, e2], observations)
        assert len(rels) == 0

    def test_multiple_co_occurrences(self):
        e1 = _make_entity(EntityType.DOMAIN, "a.com")
        e2 = _make_entity(EntityType.IP, "1.2.3.4")
        e3 = _make_entity(EntityType.EMAIL, "admin@a.com")

        observations = [
            {
                "id": "obs_1",
                "entities": ["domain:a.com", "ip:1.2.3.4", "email:admin@a.com"],
            },
        ]

        rels = detect_co_occurrences([e1, e2, e3], observations)
        # Should have 3 pairs: (a.com, 1.2.3.4), (a.com, admin@a.com), (1.2.3.4, admin@a.com)
        assert len(rels) == 3

    def test_empty_observations(self):
        e1 = _make_entity(EntityType.DOMAIN, "example.com")
        rels = detect_co_occurrences([e1], [])
        assert len(rels) == 0

    def test_shared_observations_increase_confidence(self):
        e1 = _make_entity(EntityType.DOMAIN, "example.com")
        e2 = _make_entity(EntityType.IP, "10.0.0.1")

        observations = [
            {"id": "obs_1", "entities": ["domain:example.com", "ip:10.0.0.1"]},
            {"id": "obs_2", "entities": ["domain:example.com", "ip:10.0.0.1"]},
            {"id": "obs_3", "entities": ["domain:example.com", "ip:10.0.0.1"]},
        ]

        rels = detect_co_occurrences([e1, e2], observations)
        assert len(rels) == 1
        assert rels[0].confidence > 0.5


# ── Full pipeline ─────────────────────────────────────────────────────────────


class TestResolveEntitiesPipeline:
    def test_full_pipeline(self):
        entities = [
            _make_entity(EntityType.IP, "10.0.0.1", sources=["dns"]),
            _make_entity(EntityType.IP, "10.0.0.1", sources=["whois"]),
            _make_entity(EntityType.DOMAIN, "example.com"),
        ]

        resolved, co_occur = resolve_entities(entities)
        assert len(resolved) == 2  # IP merged, domain kept

    def test_pipeline_with_observations(self):
        entities = [
            _make_entity(EntityType.DOMAIN, "example.com"),
            _make_entity(EntityType.IP, "10.0.0.1"),
        ]
        observations = [
            {"id": "obs_1", "entities": ["domain:example.com", "ip:10.0.0.1"]},
        ]

        resolved, co_occur = resolve_entities(entities, observations)
        assert len(resolved) == 2
        assert len(co_occur) == 1
