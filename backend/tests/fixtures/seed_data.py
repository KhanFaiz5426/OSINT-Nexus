"""Seed data — 3 sample investigations with known ground truth.

Task 9.8: Provides test fixtures for development, testing, and demo purposes.
These are deterministic fixtures with known expected outcomes.
"""

from __future__ import annotations

# ── Investigation 1: Domain investigation (phishing example) ────────────────

SEED_INVESTIGATION_1 = {
    "name": "Phishing Domain Analysis",
    "target": "malicious-example.com",
    "depth": "standard",
    "expected_target_type": "domain",
    "expected_entities": [
        {"type": "Domain", "value": "malicious-example.com"},
        {"type": "IP", "value": "185.220.100.252"},
        {"type": "Domain", "value": "ns1.shadyhost.net"},
        {"type": "Domain", "value": "mail.malicious-example.com"},
        {"type": "Email", "value": "admin@example.com"},
    ],
    "expected_relationships": [
        {"type": "hosted_on", "source": "Domain", "target": "IP"},
        {"type": "uses_nameserver", "source": "Domain", "target": "Domain"},
    ],
    "expected_risk_level": "high",
}

# ── Investigation 2: IP address investigation ────────────────────────────────

SEED_INVESTIGATION_2 = {
    "name": "Suspicious IP Investigation",
    "target": "185.220.100.252",
    "depth": "deep",
    "expected_target_type": "ip",
    "expected_entities": [
        {"type": "IP", "value": "185.220.100.252"},
        {"type": "ASN", "value": "AS209103"},
    ],
    "expected_relationships": [
        {"type": "belongs_to_asn", "source": "IP", "target": "ASN"},
    ],
    "expected_risk_level": "medium",
}

# ── Investigation 3: Username investigation ──────────────────────────────────

SEED_INVESTIGATION_3 = {
    "name": "Username OSINT Check",
    "target": "cyberresearcher42",
    "depth": "shallow",
    "expected_target_type": "username",
    "expected_entities": [
        {"type": "Username", "value": "cyberresearcher42"},
    ],
    "expected_relationships": [],
    "expected_risk_level": "low",
}

# ── Mock collector responses for seed data ───────────────────────────────────

SEED_COLLECTOR_RESPONSES = {
    "dns:malicious-example.com": {
        "answers": [
            {"type": "A", "data": "185.220.100.252", "ttl": 300},
            {"type": "NS", "data": "ns1.shadyhost.net"},
            {"type": "MX", "data": "mail.malicious-example.com", "priority": 10},
            {"type": "TXT", "data": "v=spf1 include:_spf.example.com ~all"},
        ],
    },
    "whois:malicious-example.com": {
        "domain_name": "malicious-example.com",
        "registrar": "PrivacyGuard",
        "registrant_name": "Privacy Protected",
        "registrant_email": "admin@example.com",
        "creation_date": "2026-08-28T00:00:00Z",
        "name_servers": ["ns1.shadyhost.net"],
    },
    "ct:malicious-example.com": {
        "certificates": [
            {
                "common_name": "malicious-example.com",
                "name_value": "malicious-example.com\nwww.malicious-example.com",
                "issuer_name": "C=US, O=Let's Encrypt, CN=R3",
                "not_before": "2026-08-28T00:00:00Z",
                "not_after": "2026-11-26T00:00:00Z",
            }
        ]
    },
    "http:malicious-example.com": {
        "url": "https://malicious-example.com",
        "status_code": 200,
        "headers": {"server": "nginx/1.18.0"},
        "title": "Secure Login",
        "technologies": [{"name": "Nginx", "source": "header:server", "version": "1.18.0"}],
    },
    "ip_asn:185.220.100.252": {
        "asn": "AS209103",
        "asn_description": "BEARSONNET",
        "country": "DE",
        "prefix": "185.220.100.0/24",
    },
}


def get_seed_investigations() -> list[dict]:
    """Return all seed investigation definitions."""
    return [
        SEED_INVESTIGATION_1,
        SEED_INVESTIGATION_2,
        SEED_INVESTIGATION_3,
    ]


def get_seed_collector_response(collector_target: str) -> dict | None:
    """Return mock collector response for a given collector:target key."""
    return SEED_COLLECTOR_RESPONSES.get(collector_target)
