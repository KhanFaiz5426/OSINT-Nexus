"""Entity extractor — extracts structured entities from OSINT collector data.

Tasks 4.5–4.8:
- 4.5: Regex patterns for domain, IP, email, ASN, URL, technology
- 4.6: Parse DNS responses into entity objects
- 4.7: Parse WHOIS responses into entity objects
- 4.8: Parse CT responses into entity objects
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.models import EntityType, RelationshipType
from app.models.processing import ExtractedEntity, ExtractedRelationship
from app.services.normalizer import (
    normalize_domain,
    normalize_email,
    normalize_ip,
    normalize_timestamp,
    normalize_url,
)

# ── Regex patterns (Task 4.5) ────────────────────────────────────────────────

_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b"
)

_IPV6_RE = re.compile(
    r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|"
    r"[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}|"
    r":(?::[0-9a-fA-F]{1,4}){1,7}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,7}:|"
    r"::(?:[0-9a-fA-F]{1,4}:){0,4}[0-9a-fA-F]{1,4}|"
    r"::"
)

_DOMAIN_RE = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)"
    r"+[a-zA-Z]{2,}\b"
)

_EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
)

_ASN_RE = re.compile(r"\bAS(\d{1,6})\b", re.IGNORECASE)

_URL_RE = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE,
)

_TECHNOLOGY_PATTERNS: list[tuple[str, str]] = [
    # Servers
    (r"\bnginx[/ ](\d[\d.]*)", "nginx"),
    (r"\bapache[/ ](\d[\d.]*)", "Apache"),
    (r"\blitespeed[/ ](\d[\d.]*)", "LiteSpeed"),
    (r"\bcaddy[/ ](\d[\d.]*)", "Caddy"),
    # Languages / frameworks
    (r"\bphp[/ ](\d[\d.]*)", "PHP"),
    (r"\bpython[/ ](\d[\d.]*)", "Python"),
    (r"\bruby[/ ](\d[\d.]*)", "Ruby"),
    (r"\bnode\.?js[/ ](\d[\d.]*)", "Node.js"),
    # CMS
    (r"\bwordpress[/ ](\d[\d.]*)", "WordPress"),
    (r"\bdrupal[/ ](\d[\d.]*)", "Drupal"),
    (r"\bjoomla[/ ](\d[\d.]*)", "Joomla"),
    # JS frameworks
    (r"\breact[/ ](\d[\d.]*)", "React"),
    (r"\bangular[/ ](\d[\d.]*)", "Angular"),
    (r"\bvue\.?js[/ ](\d[\d.]*)", "Vue.js"),
    # Databases
    (r"\bmysql[/ ](\d[\d.]*)", "MySQL"),
    (r"\bpostgresql[/ ](\d[\d.]*)", "PostgreSQL"),
    (r"\bmongodb[/ ](\d[\d.]*)", "MongoDB"),
    (r"\bredis[/ ](\d[\d.]*)", "Redis"),
    # Servers by header
    (r"X-Powered-By:\s*(\S+)", None),
]

# ── Generic regex extraction (Task 4.5) ──────────────────────────────────────


def extract_entities_from_text(
    text: str,
    *,
    source: str = "",
    evidence_id: str = "",
) -> list[ExtractedEntity]:
    """Extract domain, IP, email, ASN, URL entities from free text (Task 4.5).

    Uses regex patterns to find entities in unstructured text.

    Args:
        text: Raw text to scan.
        source: Collector name that produced this text.
        evidence_id: Observation ID for provenance.

    Returns:
        List of unique ExtractedEntity objects.
    """
    if not text:
        return []

    now = datetime.now(UTC)
    seen: dict[str, ExtractedEntity] = {}

    def _add(entity_type: EntityType, value: str) -> None:
        normalized = _normalize_entity_value(entity_type, value)
        if not normalized:
            return
        eid = f"{entity_type.value.lower()}:{normalized}"
        if eid in seen:
            seen[eid].touch(evidence_id, source)
        else:
            seen[eid] = ExtractedEntity(
                id=eid,
                entity_type=entity_type,
                value=normalized,
                confidence=0.85,
                first_seen=now,
                last_seen=now,
                sources=[source] if source else [],
                evidence_ids=[evidence_id] if evidence_id else [],
            )

    # IPs (check before domains to avoid false positives)
    for match in _IPV4_RE.finditer(text):
        _add(EntityType.IP, match.group())
    for match in _IPV6_RE.finditer(text):
        _add(EntityType.IP, match.group())

    # Emails (check before domains to avoid partial matches)
    for match in _EMAIL_RE.finditer(text):
        _add(EntityType.EMAIL, match.group())

    # ASN
    for match in _ASN_RE.finditer(text):
        asn_value = f"AS{match.group(1)}"
        _add(EntityType.ASN, asn_value)

    # URLs
    for match in _URL_RE.finditer(text):
        _add(EntityType.URL, match.group())

    # Domains (exclude items already captured as IP/email)
    for match in _DOMAIN_RE.finditer(text):
        candidate = match.group()
        # Skip if it's an IP
        if _IPV4_RE.fullmatch(candidate):
            continue
        # Skip if it's an email domain part
        if "@" in text and candidate == text.split("@")[-1].split()[0]:
            continue
        _add(EntityType.DOMAIN, candidate)

    return list(seen.values())


def extract_technologies_from_headers(
    headers: dict[str, str],
    *,
    source: str = "",
    evidence_id: str = "",
) -> list[ExtractedEntity]:
    """Extract technology entities from HTTP headers (Task 4.5).

    Checks Server, X-Powered-By, and other technology-revealing headers.
    """
    entities: list[ExtractedEntity] = []
    now = datetime.now(UTC)

    # Server header
    server = headers.get("server", headers.get("Server", ""))
    if server:
        tech_name = _parse_server_header(server)
        if tech_name:
            entities.append(
                ExtractedEntity(
                    id=f"{EntityType.TECHNOLOGY.value.lower()}:{tech_name}",
                    entity_type=EntityType.TECHNOLOGY,
                    value=tech_name,
                    confidence=0.9,
                    first_seen=now,
                    last_seen=now,
                    sources=[source] if source else [],
                    evidence_ids=[evidence_id] if evidence_id else [],
                )
            )

    # X-Powered-By header
    powered_by = headers.get("x-powered-by", headers.get("X-Powered-By", ""))
    if powered_by:
        entities.append(
            ExtractedEntity(
                id=f"{EntityType.TECHNOLOGY.value.lower()}:{powered_by.lower()}",
                entity_type=EntityType.TECHNOLOGY,
                value=powered_by,
                confidence=0.95,
                first_seen=now,
                last_seen=now,
                sources=[source] if source else [],
                evidence_ids=[evidence_id] if evidence_id else [],
            )
        )

    return entities


def _parse_server_header(server: str) -> str | None:
    """Extract technology name from Server header."""
    server = server.strip()
    if not server:
        return None
    # "nginx/1.18.0" → "nginx 1.18.0"
    match = re.match(r"([a-zA-Z]+)/(\d[\d.]*)", server)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return server.lower()


def _record_value(record: Any) -> str:
    """Extract string value from a DNS record dict or string."""
    if isinstance(record, dict):
        return str(record.get("value", record.get("data", "")))
    return str(record)


def _normalize_entity_value(entity_type: EntityType, value: str) -> str | None:
    """Normalize an extracted entity value based on its type."""
    value = value.strip()
    if not value:
        return None

    match entity_type:
        case EntityType.IP:
            return normalize_ip(value)
        case EntityType.DOMAIN | EntityType.SUBDOMAIN:
            return normalize_domain(value)
        case EntityType.EMAIL:
            return normalize_email(value)
        case EntityType.URL:
            return normalize_url(value)
        case EntityType.ASN:
            # Normalize to ASnnnnn format
            value = value.upper().strip()
            if not value.startswith("AS"):
                value = f"AS{value}"
            return value
        case EntityType.TECHNOLOGY:
            return value.lower().strip()
        case _:
            return value.strip()


# ── DNS response extraction (Task 4.6) ───────────────────────────────────────


def extract_from_dns(
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
    source: str = "dns",
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Parse DNS collector output into entities and relationships (Task 4.6).

    Handles A, AAAA, MX, NS, TXT, SOA, CAA, and PTR records.

    Returns:
        (entities, relationships) tuple.
    """
    from app.services.classifier import classify_target
    from app.models import TargetType
    from app.services.normalizer import normalize_email

    entities: dict[str, ExtractedEntity] = {}
    relationships: list[ExtractedRelationship] = []
    now = datetime.now(UTC)
    
    is_email = classify_target(target) == TargetType.EMAIL
    actual_target = target.split("@")[-1].strip() if is_email else target
    source_domain = normalize_domain(actual_target)

    def _add_entity(
        etype: EntityType, value: str, confidence: float = 0.9
    ) -> ExtractedEntity:
        norm = _normalize_entity_value(etype, value)
        if not norm:
            raise ValueError("empty entity value")
        eid = f"{etype.value.lower()}:{norm}"
        if eid not in entities:
            entities[eid] = ExtractedEntity(
                id=eid,
                entity_type=etype,
                value=norm,
                confidence=confidence,
                first_seen=now,
                last_seen=now,
                sources=[source],
                evidence_ids=[observation_id] if observation_id else [],
            )
        else:
            entities[eid].touch(observation_id, source)
        return entities[eid]

    def _add_rel(
        src: str,
        rel_type: Any,
        tgt: str,
        method: str = "",
        confidence: float = 0.9,
    ) -> None:
        rel_val = rel_type.value if hasattr(rel_type, "value") else str(rel_type)
        rid = f"{src}:{rel_val}:{tgt}"
        relationships.append(
            ExtractedRelationship(
                id=rid,
                source_entity_id=src,
                target_entity_id=tgt,
                rel_type=rel_type,
                confidence=confidence,
                evidence_ids=[observation_id] if observation_id else [],
                method=method,
            )
        )

    domain_entity = _add_entity(EntityType.DOMAIN, source_domain, 0.95)
    
    if is_email:
        email_val = normalize_email(target)
        email_entity = _add_entity(EntityType.EMAIL, email_val, 0.95)
        _add_rel(domain_entity.id, RelationshipType.ASSOCIATED_WITH_EMAIL, email_entity.id, "email_domain", confidence=1.0)

    # A records → IP entities + hosted_on relationship
    for record in raw_response.get("A", []):
        ip_val = _record_value(record)
        ip_entity = _add_entity(EntityType.IP, ip_val)
        _add_rel(domain_entity.id, RelationshipType.HOSTED_ON, ip_entity.id, "dns_a_record")

    # AAAA records
    for record in raw_response.get("AAAA", []):
        ip_val = _record_value(record)
        ip_entity = _add_entity(EntityType.IP, ip_val)
        _add_rel(domain_entity.id, RelationshipType.HOSTED_ON, ip_entity.id, "dns_aaaa_record")

    # MX records → sends_mail_via
    for record in raw_response.get("MX", []):
        if isinstance(record, dict):
            exchange = record.get("exchange", _record_value(record))
            priority = record.get("priority", "")
        else:
            exchange = str(record)
            priority = ""
        mx_entity = _add_entity(EntityType.DOMAIN, exchange)
        _add_rel(
            domain_entity.id,
            RelationshipType.SENDS_MAIL_VIA,
            mx_entity.id,
            "dns_mx_record",
        )
        if priority:
            mx_entity.properties["mx_priority"] = priority

    # NS records → uses_nameserver
    for record in raw_response.get("NS", []):
        ns_val = _record_value(record)
        ns_entity = _add_entity(EntityType.DOMAIN, ns_val)
        _add_rel(
            domain_entity.id,
            RelationshipType.USES_NAMESERVER,
            ns_entity.id,
            "dns_ns_record",
        )

    # SOA → nameserver + admin email
    soa = raw_response.get("SOA", {})
    if isinstance(soa, dict):
        mname = soa.get("mname", soa.get("data", ""))
        rname = soa.get("rname", "")
        if mname:
            ns_entity = _add_entity(EntityType.DOMAIN, mname)
            _add_rel(
                domain_entity.id,
                RelationshipType.USES_NAMESERVER,
                ns_entity.id,
                "dns_soa_mname",
            )
        if rname:
            # SOA rname is in DNS format (user.host → user@host)
            email_str = rname.replace(".", "@", 1)
            if "@" in email_str:
                parts = email_str.split("@")
                if len(parts) == 2:
                    admin_email = f"{parts[0]}@{parts[1].replace('.', '.', 1)}"
                    email_entity = _add_entity(EntityType.EMAIL, admin_email)
                    _add_rel(
                        domain_entity.id,
                        RelationshipType.REGISTERED_BY,
                        email_entity.id,
                        "dns_soa_rname",
                        confidence=0.7,
                    )

    # TXT records → extract embedded entities
    for record in raw_response.get("TXT", []):
        txt_val = _record_value(record)
        # Extract emails from SPF/DMARC
        txt_entities = extract_entities_from_text(
            txt_val, source=source, evidence_id=observation_id
        )
        for ent in txt_entities:
            if ent.id not in entities:
                entities[ent.id] = ent

    # PTR records (for reverse DNS)
    for record in raw_response.get("PTR", []):
        ptr_val = _record_value(record)
        ptr_entity = _add_entity(EntityType.DOMAIN, ptr_val)
        _add_rel(
            domain_entity.id,
            RelationshipType.HAS_PTR,
            ptr_entity.id,
            "dns_ptr_record",
        )

    return list(entities.values()), relationships


# ── WHOIS response extraction (Task 4.7) ─────────────────────────────────────


def extract_from_whois(
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
    source: str = "whois",
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Parse WHOIS collector output into entities and relationships (Task 4.7).

    Extracts: domain, registrar organization, registrant email, nameservers,
    creation date, and associated entities.

    Returns:
        (entities, relationships) tuple.
    """
    from app.services.classifier import classify_target
    from app.models import TargetType
    from app.services.normalizer import normalize_email

    entities: dict[str, ExtractedEntity] = {}
    relationships: list[ExtractedRelationship] = []
    now = datetime.now(UTC)
    
    is_email = classify_target(target) == TargetType.EMAIL
    actual_target = target.split("@")[-1].strip() if is_email else target
    source_domain = normalize_domain(actual_target)

    def _add_entity(
        etype: EntityType, value: str, confidence: float = 0.9
    ) -> ExtractedEntity:
        norm = _normalize_entity_value(etype, value)
        if not norm:
            raise ValueError("empty entity value")
        eid = f"{etype.value.lower()}:{norm}"
        if eid not in entities:
            entities[eid] = ExtractedEntity(
                id=eid,
                entity_type=etype,
                value=norm,
                confidence=confidence,
                first_seen=now,
                last_seen=now,
                sources=[source],
                evidence_ids=[observation_id] if observation_id else [],
            )
        else:
            entities[eid].touch(observation_id, source)
        return entities[eid]

    def _add_rel(
        src: str,
        rel_type: Any,
        tgt: str,
        method: str = "",
        confidence: float = 0.85,
    ) -> None:
        rel_val = rel_type.value if hasattr(rel_type, "value") else str(rel_type)
        rid = f"{src}:{rel_val}:{tgt}"
        relationships.append(
            ExtractedRelationship(
                id=rid,
                source_entity_id=src,
                target_entity_id=tgt,
                rel_type=rel_type,
                confidence=confidence,
                evidence_ids=[observation_id] if observation_id else [],
                method=method,
            )
        )

    domain_entity = _add_entity(EntityType.DOMAIN, source_domain, 0.9)
    
    if is_email:
        email_val = normalize_email(target)
        email_entity = _add_entity(EntityType.EMAIL, email_val, 0.95)
        _add_rel(domain_entity.id, RelationshipType.ASSOCIATED_WITH_EMAIL, email_entity.id, "email_domain", confidence=1.0)

    # Registrar → Organization
    registrar = raw_response.get("registrar", "")
    if registrar:
        reg_entity = _add_entity(EntityType.ORGANIZATION, registrar, 0.8)
        _add_rel(
            domain_entity.id,
            RelationshipType.REGISTERED_WITH,
            reg_entity.id,
            "whois_registrar",
        )

    # Registrant email → Email
    registrant_email = raw_response.get("registrant_email", "")
    if registrant_email and not _is_redacted(registrant_email):
        email_entity = _add_entity(EntityType.EMAIL, registrant_email, 0.75)
        _add_rel(
            domain_entity.id,
            RelationshipType.REGISTERED_BY,
            email_entity.id,
            "whois_registrant_email",
        )

    # Registrant name → Organization
    registrant_name = raw_response.get("registrant_name", "")
    if registrant_name and not _is_redacted(registrant_name):
        org_entity = _add_entity(EntityType.ORGANIZATION, registrant_name, 0.7)
        _add_rel(
            domain_entity.id,
            RelationshipType.REGISTERED_BY,
            org_entity.id,
            "whois_registrant_name",
            confidence=0.7,
        )

    # Nameservers
    nameservers = raw_response.get("nameservers", [])
    if isinstance(nameservers, str):
        nameservers = [nameservers]
    for ns in nameservers:
        if ns and ns.lower() not in ("redacted", "privacy"):
            ns_entity = _add_entity(EntityType.DOMAIN, ns, 0.9)
            _add_rel(
                domain_entity.id,
                RelationshipType.USES_NAMESERVER,
                ns_entity.id,
                "whois_nameserver",
            )

    # Dates
    creation_date = raw_response.get("creation_date")
    if creation_date:
        dt = normalize_timestamp(creation_date)
        if dt:
            domain_entity.properties["creation_date"] = dt.isoformat()

    expiry_date = raw_response.get("expiry_date") or raw_response.get("expiration_date")
    if expiry_date:
        dt = normalize_timestamp(expiry_date)
        if dt:
            domain_entity.properties["expiry_date"] = dt.isoformat()

    updated_date = raw_response.get("updated_date")
    if updated_date:
        dt = normalize_timestamp(updated_date)
        if dt:
            domain_entity.properties["updated_date"] = dt.isoformat()

    # Status
    status = raw_response.get("domain_status", "")
    if status:
        domain_entity.properties["whois_status"] = status

    return list(entities.values()), relationships


# ── Certificate Transparency extraction (Task 4.8) ──────────────────────────


def extract_from_ct(
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
    source: str = "certificate_transparency",
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Parse Certificate Transparency (crt.sh) output into entities (Task 4.8).

    Extracts: domains, subdomains, certificate entity, issuer organization.

    Returns:
        (entities, relationships) tuple.
    """
    from app.services.classifier import classify_target
    from app.models import TargetType
    from app.services.normalizer import normalize_email

    entities: dict[str, ExtractedEntity] = {}
    relationships: list[ExtractedRelationship] = []
    now = datetime.now(UTC)
    
    is_email = classify_target(target) == TargetType.EMAIL
    actual_target = target.split("@")[-1].strip() if is_email else target
    source_domain = normalize_domain(actual_target)

    def _add_entity(
        etype: EntityType, value: str, confidence: float = 0.9
    ) -> ExtractedEntity:
        norm = _normalize_entity_value(etype, value)
        if not norm:
            raise ValueError("empty entity value")
        eid = f"{etype.value.lower()}:{norm}"
        if eid not in entities:
            entities[eid] = ExtractedEntity(
                id=eid,
                entity_type=etype,
                value=norm,
                confidence=confidence,
                first_seen=now,
                last_seen=now,
                sources=[source],
                evidence_ids=[observation_id] if observation_id else [],
            )
        else:
            entities[eid].touch(observation_id, source)
        return entities[eid]

    def _add_rel(
        src: str,
        rel_type: Any,
        tgt: str,
        method: str = "",
        confidence: float = 0.9,
    ) -> None:
        rel_val = rel_type.value if hasattr(rel_type, "value") else str(rel_type)
        rid = f"{src}:{rel_val}:{tgt}"
        relationships.append(
            ExtractedRelationship(
                id=rid,
                source_entity_id=src,
                target_entity_id=tgt,
                rel_type=rel_type,
                confidence=confidence,
                evidence_ids=[observation_id] if observation_id else [],
                method=method,
            )
        )

    domain_entity = _add_entity(EntityType.DOMAIN, source_domain, 0.95)
    
    if is_email:
        email_val = normalize_email(target)
        email_entity = _add_entity(EntityType.EMAIL, email_val, 0.95)
        _add_rel(domain_entity.id, RelationshipType.ASSOCIATED_WITH_EMAIL, email_entity.id, "email_domain", confidence=1.0)

    # Certificates
    certificates = raw_response.get("certificates", [])
    for cert in certificates:
        if not isinstance(cert, dict):
            continue

        cert_id = cert.get("id") or cert.get("issuer_name", "unknown")
        cert_entity = _add_entity(EntityType.CERTIFICATE, str(cert_id), 0.9)

        _add_rel(
            domain_entity.id,
            RelationshipType.COVERED_BY_CERTIFICATE,
            cert_entity.id,
            "ct_certificate",
        )

        # Issuer → Organization
        issuer_name = cert.get("issuer_name", "")
        if issuer_name:
            issuer_org = _extract_issuer_org(issuer_name)
            if issuer_org:
                org_entity = _add_entity(EntityType.ORGANIZATION, issuer_org, 0.85)
                _add_rel(
                    cert_entity.id,
                    RelationshipType.ISSUED_BY,
                    org_entity.id,
                    "ct_issuer",
                )

        # Names in SANs → subdomains
        name_value = cert.get("name_value", "")
        if name_value:
            for name in name_value.split("\n"):
                name = name.strip().lower()
                if name and name != source_domain:
                    # Subdomain if it ends with source_domain
                    if name.endswith(f".{source_domain}") or name == source_domain:
                        sub_entity = _add_entity(EntityType.SUBDOMAIN, name, 0.9)
                        _add_rel(
                            domain_entity.id,
                            RelationshipType.HAS_SUBDOMAIN,
                            sub_entity.id,
                            "ct_san",
                        )
                    else:
                        # Different domain — could be related via shared cert
                        other_domain = _add_entity(EntityType.DOMAIN, name, 0.75)
                        _add_rel(
                            other_domain.id,
                            RelationshipType.COVERED_BY_CERTIFICATE,
                            cert_entity.id,
                            "ct_san",
                            confidence=0.8,
                        )

    return list(entities.values()), relationships


def _is_redacted(value: str) -> bool:
    """Check if a WHOIS value indicates redacted/privacy-protected data."""
    lower = value.lower()
    redacted_keywords = ("redacted", "privacy", "whoisguard", "protected", "redacted for")
    return any(kw in lower for kw in redacted_keywords)


def _extract_issuer_org(issuer_name: str) -> str | None:
    """Extract organization name from a certificate issuer DN.

    Example: 'CN = Let's Encrypt Authority X3, O = Let's Encrypt' → 'Let's Encrypt'
    """
    for part in issuer_name.split(","):
        part = part.strip()
        upper = part.upper()
        if upper.startswith("O=") or upper.startswith("O ="):
            # Find the value after '=' or '='
            idx = part.index("=")
            return part[idx + 1:].strip()
    # Fallback: use CN
    for part in issuer_name.split(","):
        part = part.strip()
        upper = part.upper()
        if upper.startswith("CN=") or upper.startswith("CN ="):
            idx = part.index("=")
            return part[idx + 1:].strip()
    return None
