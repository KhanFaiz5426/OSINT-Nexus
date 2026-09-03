"""Tests for entity extractor (Tasks 4.5–4.8)."""


from app.models import EntityType
from app.services.extractor import (
    extract_entities_from_text,
    extract_from_ct,
    extract_from_dns,
    extract_from_whois,
    extract_technologies_from_headers,
)

# ── Task 4.5: Regex entity extraction ────────────────────────────────────────


class TestExtractEntitiesFromText:
    def test_extract_ipv4(self):
        text = "The server is at 192.168.1.1 and also 10.0.0.1"
        entities = extract_entities_from_text(text)
        ips = [e for e in entities if e.entity_type == EntityType.IP]
        assert len(ips) == 2
        values = {e.value for e in ips}
        assert "192.168.1.1" in values
        assert "10.0.0.1" in values

    def test_extract_ipv6(self):
        text = "IPv6 address: 2001:db8::1"
        entities = extract_entities_from_text(text)
        ips = [e for e in entities if e.entity_type == EntityType.IP]
        assert len(ips) == 1
        assert ips[0].value == "2001:db8::1"

    def test_extract_domain(self):
        text = "Visit example.com for more info"
        entities = extract_entities_from_text(text)
        domains = [e for e in entities if e.entity_type == EntityType.DOMAIN]
        assert len(domains) >= 1
        assert any(e.value == "example.com" for e in domains)

    def test_extract_email(self):
        text = "Contact admin@example.com for details"
        entities = extract_entities_from_text(text)
        emails = [e for e in entities if e.entity_type == EntityType.EMAIL]
        assert len(emails) == 1
        assert emails[0].value == "admin@example.com"

    def test_extract_asn(self):
        text = "Hosted in AS12345 by Example Corp"
        entities = extract_entities_from_text(text)
        asns = [e for e in entities if e.entity_type == EntityType.ASN]
        assert len(asns) == 1
        assert asns[0].value == "AS12345"

    def test_extract_url(self):
        text = "See https://example.com/path?q=1 for details"
        entities = extract_entities_from_text(text)
        urls = [e for e in entities if e.entity_type == EntityType.URL]
        assert len(urls) == 1
        assert "example.com/path" in urls[0].value

    def test_extract_mixed(self):
        text = (
            "Domain evil.com resolves to 185.220.100.252. "
            "Contact admin@evil.com. Hosted in AS209103."
        )
        entities = extract_entities_from_text(text)
        types = {e.entity_type for e in entities}
        assert EntityType.DOMAIN in types
        assert EntityType.IP in types
        assert EntityType.EMAIL in types
        assert EntityType.ASN in types

    def test_empty_text(self):
        assert extract_entities_from_text("") == []

    def test_no_entities(self):
        assert extract_entities_from_text("just some random text") == []

    def test_deduplication(self):
        text = "10.0.0.1 and also 10.0.0.1 again"
        entities = extract_entities_from_text(text, source="dns", evidence_id="obs_1")
        ips = [e for e in entities if e.entity_type == EntityType.IP]
        assert len(ips) == 1

    def test_source_tracking(self):
        text = "Visit example.com"
        entities = extract_entities_from_text(text, source="dns", evidence_id="obs_1")
        assert len(entities) >= 1
        assert entities[0].sources == ["dns"]
        assert entities[0].evidence_ids == ["obs_1"]


class TestExtractTechnologiesFromHeaders:
    def test_server_header(self):
        headers = {"Server": "nginx/1.18.0"}
        entities = extract_technologies_from_headers(headers, source="http")
        assert len(entities) == 1
        assert entities[0].entity_type == EntityType.TECHNOLOGY
        assert "nginx" in entities[0].value

    def test_x_powered_by(self):
        headers = {"X-Powered-By": "PHP/8.1.2"}
        entities = extract_technologies_from_headers(headers, source="http")
        assert len(entities) == 1
        assert "php" in entities[0].value.lower()

    def test_both_headers(self):
        headers = {"Server": "Apache/2.4.41", "X-Powered-By": "PHP/7.4.3"}
        entities = extract_technologies_from_headers(headers, source="http")
        assert len(entities) == 2

    def test_empty_headers(self):
        assert extract_technologies_from_headers({}) == []


# ── Task 4.6: DNS response extraction ────────────────────────────────────────


class TestExtractFromDNS:
    def test_a_records(self):
        raw = {"A": [{"data": "93.184.216.34"}]}
        entities, rels = extract_from_dns("example.com", raw, observation_id="obs_1")

        ips = [e for e in entities if e.entity_type == EntityType.IP]
        assert len(ips) == 1
        assert ips[0].value == "93.184.216.34"

        hosted = [r for r in rels if r.rel_type.value == "hosted_on"]
        assert len(hosted) == 1

    def test_mx_records(self):
        raw = {"MX": [{"exchange": "mail.example.com", "priority": 10}]}
        entities, rels = extract_from_dns("example.com", raw, observation_id="obs_1")

        mx_domains = [
            e for e in entities
            if e.entity_type == EntityType.DOMAIN and e.value == "mail.example.com"
        ]
        assert len(mx_domains) == 1

        mail_via = [r for r in rels if r.rel_type.value == "sends_mail_via"]
        assert len(mail_via) == 1

    def test_ns_records(self):
        raw = {"NS": [{"data": "ns1.example.com"}, {"data": "ns2.example.com"}]}
        entities, rels = extract_from_dns("example.com", raw, observation_id="obs_1")

        ns_entities = [
            e for e in entities
            if e.entity_type == EntityType.DOMAIN
            and e.value in ("ns1.example.com", "ns2.example.com")
        ]
        assert len(ns_entities) == 2

        ns_rels = [r for r in rels if r.rel_type.value == "uses_nameserver"]
        assert len(ns_rels) == 2

    def test_soa_record(self):
        raw = {
            "SOA": {
                "mname": "ns1.example.com",
                "rname": "admin.example.com",
            }
        }
        entities, rels = extract_from_dns("example.com", raw, observation_id="obs_1")

        # Should have SOA mname as nameserver
        ns_rels = [r for r in rels if r.rel_type.value == "uses_nameserver"]
        assert len(ns_rels) >= 1

    def test_txt_records_extract_entities(self):
        raw = {"TXT": [{"data": "v=spf1 include:_spf.google.com ~all"}]}
        entities, rels = extract_from_dns("example.com", raw, observation_id="obs_1")

        # Should extract domain from SPF
        domains = [e for e in entities if e.entity_type == EntityType.DOMAIN]
        assert len(domains) >= 1

    def test_empty_response(self):
        raw = {}
        entities, rels = extract_from_dns("example.com", raw)
        # Should still have the domain entity
        domains = [e for e in entities if e.entity_type == EntityType.DOMAIN]
        assert len(domains) == 1
        assert rels == []


# ── Task 4.7: WHOIS response extraction ──────────────────────────────────────


class TestExtractFromWHOIS:
    def test_registrar(self):
        raw = {"registrar": "GoDaddy LLC"}
        entities, rels = extract_from_whois("example.com", raw, observation_id="obs_1")

        orgs = [
            e for e in entities
            if e.entity_type == EntityType.ORGANIZATION and e.value == "GoDaddy LLC"
        ]
        assert len(orgs) == 1

        reg_with = [r for r in rels if r.rel_type.value == "registered_with"]
        assert len(reg_with) == 1

    def test_registrant_email(self):
        raw = {"registrant_email": "admin@example.com"}
        entities, rels = extract_from_whois("example.com", raw, observation_id="obs_1")

        emails = [
            e for e in entities
            if e.entity_type == EntityType.EMAIL and e.value == "admin@example.com"
        ]
        assert len(emails) == 1

        reg_by = [r for r in rels if r.rel_type.value == "registered_by"]
        assert len(reg_by) == 1

    def test_privacy_protection(self):
        raw = {"registrant_email": "REDACTED FOR PRIVACY"}
        entities, rels = extract_from_whois("example.com", raw, observation_id="obs_1")

        emails = [e for e in entities if e.entity_type == EntityType.EMAIL]
        assert len(emails) == 0

    def test_nameservers(self):
        raw = {"nameservers": ["ns1.example.com", "ns2.example.com"]}
        entities, rels = extract_from_whois("example.com.com", raw, observation_id="obs_1")

        ns_rels = [r for r in rels if r.rel_type.value == "uses_nameserver"]
        assert len(ns_rels) == 2

    def test_dates(self):
        raw = {
            "creation_date": "2020-01-15",
            "expiry_date": "2030-01-15",
        }
        entities, _ = extract_from_whois("example.com", raw, observation_id="obs_1")

        domain = [e for e in entities if e.entity_type == EntityType.DOMAIN]
        assert len(domain) == 1
        assert "creation_date" in domain[0].properties
        assert "expiry_date" in domain[0].properties

    def test_empty_response(self):
        raw = {}
        entities, rels = extract_from_whois("example.com", raw)
        domains = [e for e in entities if e.entity_type == EntityType.DOMAIN]
        assert len(domains) == 1
        assert rels == []


# ── Task 4.8: CT response extraction ─────────────────────────────────────────


class TestExtractFromCT:
    def test_certificate_extraction(self):
        raw = {
            "certificates": [
                {
                    "id": "abc123",
                    "issuer_name": "CN = Let's Encrypt Authority X3, O = Let's Encrypt",
                    "name_value": "example.com\nwww.example.com",
                }
            ]
        }
        entities, rels = extract_from_ct("example.com", raw, observation_id="obs_1")

        certs = [e for e in entities if e.entity_type == EntityType.CERTIFICATE]
        assert len(certs) == 1

        covered = [r for r in rels if r.rel_type.value == "covered_by_certificate"]
        assert len(covered) == 1

    def test_issuer_organization(self):
        raw = {
            "certificates": [
                {
                    "id": "cert1",
                    "issuer_name": "CN = DigiCert SHA2, O = DigiCert Inc",
                }
            ]
        }
        entities, _ = extract_from_ct("example.com", raw, observation_id="obs_1")

        orgs = [
            e for e in entities
            if e.entity_type == EntityType.ORGANIZATION and "DigiCert" in e.value
        ]
        assert len(orgs) == 1

    def test_subdomains_from_san(self):
        raw = {
            "certificates": [
                {
                    "id": "cert1",
                    "name_value": "shop.example.com\nlogin.example.com",
                }
            ]
        }
        entities, rels = extract_from_ct("example.com", raw, observation_id="obs_1")

        subdomains = [e for e in entities if e.entity_type == EntityType.SUBDOMAIN]
        assert len(subdomains) == 2

        has_sub = [r for r in rels if r.rel_type.value == "has_subdomain"]
        assert len(has_sub) == 2

    def test_empty_certificates(self):
        raw = {"certificates": []}
        entities, rels = extract_from_ct("example.com", raw)
        domains = [e for e in entities if e.entity_type == EntityType.DOMAIN]
        assert len(domains) == 1
        assert rels == []
