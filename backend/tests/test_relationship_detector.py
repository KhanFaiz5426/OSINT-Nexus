"""Tests for relationship detector (Task 4.12)."""

from app.models import EntityType, RelationshipType
from app.models.processing import ExtractedEntity
from app.services.relationship_detector import detect_relationships


def _make_entity(entity_type: EntityType, value: str) -> ExtractedEntity:
    return ExtractedEntity(
        id=f"{entity_type.value.lower()}:{value}",
        entity_type=entity_type,
        value=value,
        confidence=0.9,
        sources=["dns"],
        evidence_ids=["obs_1"],
    )


class TestDetectRelationships:
    def test_dns_a_record(self):
        entities = [
            _make_entity(EntityType.DOMAIN, "example.com"),
            _make_entity(EntityType.IP, "93.184.216.34"),
        ]
        raw_results = [
            {
                "collector_name": "dns",
                "target": "example.com",
                "raw_response": {"A": [{"data": "93.184.216.34"}]},
                "observation_id": "obs_1",
            },
        ]

        rels = detect_relationships(entities, raw_results)
        hosted = [r for r in rels if r.rel_type == RelationshipType.HOSTED_ON]
        assert len(hosted) == 1
        assert hosted[0].source_entity_id == "domain:example.com"
        assert hosted[0].target_entity_id == "ip:93.184.216.34"

    def test_dns_ns_record(self):
        entities = [
            _make_entity(EntityType.DOMAIN, "example.com"),
            _make_entity(EntityType.DOMAIN, "ns1.example.com"),
        ]
        raw_results = [
            {
                "collector_name": "dns",
                "target": "example.com",
                "raw_response": {"NS": [{"data": "ns1.example.com"}]},
                "observation_id": "obs_1",
            },
        ]

        rels = detect_relationships(entities, raw_results)
        ns_rels = [r for r in rels if r.rel_type == RelationshipType.USES_NAMESERVER]
        assert len(ns_rels) == 1

    def test_dns_mx_record(self):
        entities = [
            _make_entity(EntityType.DOMAIN, "example.com"),
            _make_entity(EntityType.DOMAIN, "mail.example.com"),
        ]
        raw_results = [
            {
                "collector_name": "dns",
                "target": "example.com",
                "raw_response": {"MX": [{"exchange": "mail.example.com", "priority": 10}]},
                "observation_id": "obs_1",
            },
        ]

        rels = detect_relationships(entities, raw_results)
        mx_rels = [r for r in rels if r.rel_type == RelationshipType.SENDS_MAIL_VIA]
        assert len(mx_rels) == 1

    def test_whois_registrant_email(self):
        entities = [
            _make_entity(EntityType.DOMAIN, "example.com"),
            _make_entity(EntityType.EMAIL, "admin@example.com"),
        ]
        raw_results = [
            {
                "collector_name": "whois",
                "target": "example.com",
                "raw_response": {"registrant_email": "admin@example.com"},
                "observation_id": "obs_1",
            },
        ]

        rels = detect_relationships(entities, raw_results)
        reg_by = [r for r in rels if r.rel_type == RelationshipType.REGISTERED_BY]
        assert len(reg_by) == 1

    def test_whois_registrar(self):
        entities = [
            _make_entity(EntityType.DOMAIN, "example.com"),
            _make_entity(EntityType.ORGANIZATION, "GoDaddy LLC"),
        ]
        raw_results = [
            {
                "collector_name": "whois",
                "target": "example.com",
                "raw_response": {"registrar": "GoDaddy LLC"},
                "observation_id": "obs_1",
            },
        ]

        rels = detect_relationships(entities, raw_results)
        reg_with = [r for r in rels if r.rel_type == RelationshipType.REGISTERED_WITH]
        assert len(reg_with) == 1

    def test_ip_to_asn(self):
        entities = [
            _make_entity(EntityType.IP, "10.0.0.1"),
            _make_entity(EntityType.ASN, "AS12345"),
        ]
        raw_results = [
            {
                "collector_name": "ip_to_asn",
                "target": "10.0.0.1",
                "raw_response": {"asn": "AS12345"},
                "observation_id": "obs_1",
            },
        ]

        rels = detect_relationships(entities, raw_results)
        asn_rels = [r for r in rels if r.rel_type == RelationshipType.BELONGS_TO_ASN]
        assert len(asn_rels) == 1

    def test_http_technology(self):
        entities = [
            _make_entity(EntityType.DOMAIN, "example.com"),
            _make_entity(EntityType.TECHNOLOGY, "nginx"),
        ]
        raw_results = [
            {
                "collector_name": "http",
                "target": "example.com",
                "raw_response": {"technologies": ["nginx"]},
                "observation_id": "obs_1",
            },
        ]

        rels = detect_relationships(entities, raw_results)
        tech_rels = [r for r in rels if r.rel_type == RelationshipType.USES_TECHNOLOGY]
        assert len(tech_rels) == 1

    def test_ct_certificate(self):
        entities = [
            _make_entity(EntityType.DOMAIN, "example.com"),
            _make_entity(EntityType.CERTIFICATE, "cert123"),
        ]
        raw_results = [
            {
                "collector_name": "certificate_transparency",
                "target": "example.com",
                "raw_response": {"certificates": [{"id": "cert123"}]},
                "observation_id": "obs_1",
            },
        ]

        rels = detect_relationships(entities, raw_results)
        cert_rels = [r for r in rels if r.rel_type == RelationshipType.COVERED_BY_CERTIFICATE]
        assert len(cert_rels) == 1

    def test_no_relationships_when_entities_missing(self):
        entities = [_make_entity(EntityType.DOMAIN, "example.com")]
        raw_results = [
            {
                "collector_name": "dns",
                "target": "example.com",
                "raw_response": {"A": [{"data": "10.0.0.1"}]},
                "observation_id": "obs_1",
            },
        ]

        rels = detect_relationships(entities, raw_results)
        # IP entity doesn't exist, so no relationship
        assert len(rels) == 0

    def test_deduplication(self):
        entities = [
            _make_entity(EntityType.DOMAIN, "example.com"),
            _make_entity(EntityType.IP, "10.0.0.1"),
        ]
        raw_results = [
            {
                "collector_name": "dns",
                "target": "example.com",
                "raw_response": {"A": [{"data": "10.0.0.1"}]},
                "observation_id": "obs_1",
            },
            {
                "collector_name": "dns",
                "target": "example.com",
                "raw_response": {"A": [{"data": "10.0.0.1"}]},
                "observation_id": "obs_2",
            },
        ]

        rels = detect_relationships(entities, raw_results)
        hosted = [r for r in rels if r.rel_type == RelationshipType.HOSTED_ON]
        assert len(hosted) == 1  # Deduplicated

    def test_empty_raw_results(self):
        entities = [_make_entity(EntityType.DOMAIN, "example.com")]
        rels = detect_relationships(entities, [])
        assert rels == []
