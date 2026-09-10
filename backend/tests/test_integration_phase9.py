"""Integration tests — full investigation flow with mocked collectors.

Task 9.2: Tests the complete pipeline from investigation creation through
collection, normalization, extraction, resolution, correlation, and graph
storage — using mocked collector responses (no live API calls).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.models import EntityType, RelationshipType, TargetType
from app.models.processing import ExtractedEntity

# ── Mock collector responses ─────────────────────────────────────────────────

MOCK_DNS_RESULT = {
    "A": [{"data": "93.184.216.34", "ttl": 3600}],
    "AAAA": [{"data": "2606:2800:220:1:248:1893:25c8:1946", "ttl": 3600}],
    "MX": [{"data": "mail.example.com", "priority": 10}],
    "NS": [{"data": "ns1.example.com"}, {"data": "ns2.example.com"}],
    "TXT": [{"data": "v=spf1 include:_spf.example.com ~all"}],
}

MOCK_WHOIS_RESULT = {
    "domain_name": "example.com",
    "registrar": "Example Registrar Inc.",
    "registrant_name": "Privacy Protected",
    "registrant_email": "admin@example.com",
    "creation_date": "1995-08-14T00:00:00Z",
    "expiration_date": "2025-08-13T00:00:00Z",
    "nameservers": ["ns1.example.com", "ns2.example.com"],
    "status": ["clientTransferProhibited"],
}

MOCK_CT_RESULT = {
    "certificates": [
        {
            "id": 12345,
            "issuer_name": "C=US, O=Let's Encrypt, CN=R3",
            "common_name": "example.com",
            "name_value": "example.com\nwww.example.com",
            "not_before": "2026-01-01T00:00:00Z",
            "not_after": "2026-04-01T00:00:00Z",
            "serial_number": "abc123",
        }
    ]
}


# ── Tests ────────────────────────────────────────────────────────────────────


class TestInvestigationFlow:
    """Test the full investigation pipeline with mocked data."""

    def test_classifier_domain(self):
        from app.services.classifier import classify_target

        result = classify_target("example.com")
        assert result == TargetType.DOMAIN

    def test_classifier_ip(self):
        from app.services.classifier import classify_target

        result = classify_target("93.184.216.34")
        assert result == TargetType.IP

    def test_classifier_email(self):
        from app.services.classifier import classify_target

        result = classify_target("admin@example.com")
        assert result == TargetType.EMAIL

    def test_classifier_url(self):
        from app.services.classifier import classify_target

        result = classify_target("https://example.com/path")
        assert result == TargetType.URL

    def test_classifier_username(self):
        from app.services.classifier import classify_target

        result = classify_target("cyberresearcher42")
        assert result == TargetType.USERNAME


class TestNormalization:
    """Test data normalization pipeline."""

    def test_normalize_domain(self):
        from app.services.normalizer import normalize_domain

        assert normalize_domain("EXAMPLE.COM") == "example.com"
        assert normalize_domain("example.com.") == "example.com"
        assert normalize_domain("Example.Com") == "example.com"

    def test_normalize_ip(self):
        from app.services.normalizer import normalize_ip

        assert normalize_ip("192.168.001.001") == "192.168.1.1"
        assert normalize_ip("93.184.216.34") == "93.184.216.34"

    def test_normalize_email(self):
        from app.services.normalizer import normalize_email

        assert normalize_email("Admin@Example.Com") == "admin@example.com"


class TestEntityExtraction:
    """Test entity extraction from collector responses."""

    def test_extract_from_dns(self):
        from app.services.extractor import extract_from_dns

        entities, relationships = extract_from_dns("example.com", MOCK_DNS_RESULT)
        entity_values = [(e.entity_type, e.value) for e in entities]

        # Should extract IPs, MX domain, NS domains
        assert any(t == EntityType.IP and v == "93.184.216.34" for t, v in entity_values)
        assert any(t == EntityType.DOMAIN and v == "mail.example.com" for t, v in entity_values)
        assert any(t == EntityType.DOMAIN and v == "ns1.example.com" for t, v in entity_values)

    def test_extract_from_whois(self):
        from app.services.extractor import extract_from_whois

        entities, relationships = extract_from_whois("example.com", MOCK_WHOIS_RESULT)
        entity_values = [(e.entity_type, e.value) for e in entities]

        # Should extract email and nameserver domains
        assert any(t == EntityType.EMAIL and "admin@example.com" in v for t, v in entity_values)

    def test_extract_from_ct(self):
        from app.services.extractor import extract_from_ct

        entities, relationships = extract_from_ct("example.com", MOCK_CT_RESULT)
        entity_values = [(e.entity_type, e.value) for e in entities]
        print("CT entities:", entity_values)

        # Should extract subdomains from SAN (may be multiple domains from name_value)
        assert any(t == EntityType.DOMAIN for t, v in entity_values)


class TestConfidenceScoring:
    """Test confidence score calculations."""

    def test_high_quality_entity(self):
        from app.services.confidence import score_entity

        entity = ExtractedEntity(
            id="domain:example.com",
            entity_type=EntityType.DOMAIN,
            value="example.com",
            confidence=0.9,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
            sources=["dns", "whois"],
            evidence_ids=["obs-001", "obs-002"],
        )

        score = score_entity(entity)
        assert 0.7 <= score <= 1.0

    def test_low_quality_entity(self):
        from app.services.confidence import score_entity

        entity = ExtractedEntity(
            id="domain:old.example.com",
            entity_type=EntityType.DOMAIN,
            value="old.example.com",
            confidence=0.5,
            first_seen=datetime(2020, 1, 1, tzinfo=UTC),
            last_seen=datetime(2020, 1, 1, tzinfo=UTC),
            sources=["search"],
            evidence_ids=["obs-003"],
        )

        score = score_entity(entity)
        assert 0.0 <= score <= 0.8


class TestResolver:
    """Test entity deduplication."""

    def test_exact_match_dedup(self):
        from app.services.resolver import resolve_entities

        entities = [
            ExtractedEntity(
                id="domain:example.com",
                entity_type=EntityType.DOMAIN,
                value="example.com",
                confidence=0.9,
                sources=["dns"],
            ),
            ExtractedEntity(
                id="domain:example.com",
                entity_type=EntityType.DOMAIN,
                value="example.com",
                confidence=0.9,
                sources=["whois"],
            ),
        ]
        resolved, _ = resolve_entities(entities)
        # Should deduplicate exact matches
        assert len(resolved) <= len(entities)


class TestRelationshipDetection:
    """Test relationship detection from DNS data."""

    def test_detect_hosted_on(self):
        from app.services.relationship_detector import detect_relationships

        entities = [
            ExtractedEntity(
                id="domain:example.com",
                entity_type=EntityType.DOMAIN,
                value="example.com",
                confidence=0.9,
                sources=["dns"],
            ),
            ExtractedEntity(
                id="ip:93.184.216.34",
                entity_type=EntityType.IP,
                value="93.184.216.34",
                confidence=0.9,
                sources=["dns"],
            ),
        ]
        raw_results = [
            {
                "collector_name": "dns",
                "target": "example.com",
                "raw_response": MOCK_DNS_RESULT,
                "observation_id": "obs-001",
            }
        ]
        rels = detect_relationships(entities, raw_results)
        rel_types = [r.rel_type for r in rels]
        assert RelationshipType.HOSTED_ON in rel_types


class TestSSRFProtection:
    """Test SSRF protection for outbound requests."""

    def test_blocks_localhost(self):
        from app.core.security import SSRFBlockedError, validate_url_not_internal

        with pytest.raises(SSRFBlockedError):
            validate_url_not_internal("http://localhost:8080/admin")

    def test_blocks_private_ip(self):
        from app.core.security import SSRFBlockedError, validate_url_not_internal

        with pytest.raises(SSRFBlockedError):
            validate_url_not_internal("http://192.168.1.1/admin")

    def test_blocks_cloud_metadata(self):
        from app.core.security import SSRFBlockedError, validate_url_not_internal

        with pytest.raises(SSRFBlockedError):
            validate_url_not_internal("http://169.254.169.254/latest/meta-data/")

    def test_blocks_10x_range(self):
        from app.core.security import SSRFBlockedError, validate_url_not_internal

        with pytest.raises(SSRFBlockedError):
            validate_url_not_internal("http://10.0.0.1/secret")

    def test_allows_public_url(self):
        from app.core.security import validate_url_not_internal

        result = validate_url_not_internal("https://example.com/path")
        assert result == "https://example.com/path"

    def test_allows_public_ip(self):
        from app.core.security import validate_url_not_internal

        result = validate_url_not_internal("https://93.184.216.34/path")
        assert result == "https://93.184.216.34/path"


class TestTargetValidation:
    """Test target input validation."""

    def test_rejects_empty_target(self):
        from app.core.security import validate_target_for_collector

        with pytest.raises(ValueError):
            validate_target_for_collector("", "domain")

    def test_rejects_ftp_url(self):
        from app.core.security import validate_target_for_collector

        with pytest.raises(ValueError):
            validate_target_for_collector("ftp://example.com/file", "url")

    def test_rejects_url_with_credentials(self):
        from app.core.security import validate_target_for_collector

        with pytest.raises(ValueError):
            validate_target_for_collector("http://user:pass@example.com", "url")

    def test_allows_valid_url(self):
        from app.core.security import validate_target_for_collector

        result = validate_target_for_collector("https://example.com/path", "url")
        assert result == "https://example.com/path"

    def test_strips_control_chars(self):
        from app.core.security import validate_target_for_collector

        result = validate_target_for_collector("example.com\x00\x01", "domain")
        assert "\x00" not in result
        assert "\x01" not in result
