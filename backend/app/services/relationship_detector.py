"""Relationship detector — extracts relationships from normalized entity data.

Task 4.12: Detect relationships between entities from collected data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models import EntityType, RelationshipType
from app.models.processing import ExtractedEntity, ExtractedRelationship


def _record_value(record: Any) -> str:
    """Extract string value from a DNS record dict or string."""
    if isinstance(record, dict):
        return str(record.get("value", record.get("data", "")))
    return str(record)


def detect_relationships(
    entities: list[ExtractedEntity],
    raw_results: list[dict[str, Any]],
    *,
    investigation_id: str = "",
) -> list[ExtractedRelationship]:
    """Detect relationships between entities from collector outputs (Task 4.12).

    Analyzes raw collector responses to build direct structural relationships:
    - DNS: domain → IP (hosted_on), domain → NS (uses_nameserver),
           domain → MX (sends_mail_via)
    - WHOIS: domain → registrant (registered_by), domain → registrar (registered_with)
    - CT: domain → certificate (covered_by_certificate), cert → issuer (issued_by)
    - IP-to-ASN: IP → ASN (belongs_to_asn), ASN → org (operated_by)
    - HTTP: domain → technology (uses_technology)
    - Threat Intel: domain/IP → threat indicator (associated_with_threat)

    Args:
        entities: Resolved entity list.
        raw_results: List of raw collector responses (dicts with 'collector_name',
                     'target', 'raw_response' keys).
        investigation_id: Investigation ID for provenance.

    Returns:
        List of detected relationships.
    """
    now = datetime.now(UTC)
    relationships: list[ExtractedRelationship] = []
    entity_lookup = {e.id: e for e in entities}
    seen: set[str] = set()

    def _add_rel(
        src_id: str,
        rel_type: RelationshipType,
        tgt_id: str,
        method: str = "",
        confidence: float = 0.85,
        evidence_ids: list[str] | None = None,
    ) -> None:
        """Add a relationship if not already seen."""
        # Ensure consistent ordering for dedup
        pair = tuple(sorted([src_id, tgt_id]))
        key = f"{pair[0]}:{rel_type.value}:{pair[1]}"
        if key in seen:
            return
        seen.add(key)

        if src_id not in entity_lookup or tgt_id not in entity_lookup:
            return

        relationships.append(
            ExtractedRelationship(
                id=key,
                source_entity_id=src_id,
                target_entity_id=tgt_id,
                rel_type=rel_type,
                confidence=confidence,
                evidence_ids=evidence_ids or [],
                discovered_at=now,
                method=method,
            )
        )

    def _find_entity(etype: EntityType, value: str) -> ExtractedEntity | None:
        """Find an entity by type and normalized value."""
        eid = f"{etype.value.lower()}:{value}"
        return entity_lookup.get(eid)

    for result in raw_results:
        collector = result.get("collector_name", "")
        raw_response = result.get("raw_response", {})
        target = result.get("target", "")
        obs_id = result.get("observation_id", "")

        if collector == "dns":
            _process_dns_relationships(target, raw_response, _find_entity, _add_rel, obs_id)
        elif collector == "whois":
            _process_whois_relationships(target, raw_response, _find_entity, _add_rel, obs_id)
        elif collector == "certificate_transparency":
            _process_ct_relationships(target, raw_response, _find_entity, _add_rel, obs_id)
        elif collector == "ip_to_asn":
            _process_ip_asn_relationships(target, raw_response, _find_entity, _add_rel, obs_id)
        elif collector == "http":
            _process_http_relationships(target, raw_response, _find_entity, _add_rel, obs_id)
        elif collector == "threat_intel":
            _process_threat_relationships(target, raw_response, _find_entity, _add_rel, obs_id)
        elif collector == "github":
            _process_github_relationships(target, raw_response, _find_entity, _add_rel, obs_id)

        # Fix for email targets: ensure relationship between Email and its Domain
        from app.models import EntityType, RelationshipType, TargetType
        from app.services.classifier import classify_target

        if classify_target(target) == TargetType.EMAIL:
            from app.services.normalizer import normalize_domain, normalize_email

            email_val = normalize_email(target)
            domain_val = normalize_domain(target.split("@")[-1])

            email_entity = _find_entity(EntityType.EMAIL, email_val)
            domain_entity = _find_entity(EntityType.DOMAIN, domain_val)

            if email_entity and domain_entity:
                _add_rel(
                    email_entity.id,
                    RelationshipType.ASSOCIATED_WITH_EMAIL,  # Reverse relation
                    domain_entity.id,
                    "target_email_domain",
                    1.0,
                    [obs_id] if obs_id else [],
                )

    return relationships


# ── Per-collector relationship processors ─────────────────────────────────────


def _process_dns_relationships(
    target: str,
    raw: dict[str, Any],
    find_entity: Any,
    add_rel: Any,
    obs_id: str,
) -> None:
    """Process DNS records for relationships."""
    from app.services.normalizer import normalize_domain

    domain = normalize_domain(target)
    domain_entity = find_entity(EntityType.DOMAIN, domain)
    if not domain_entity:
        return

    evidence = [obs_id] if obs_id else []

    # A/AAAA → hosted_on
    for record_type in ("A", "AAAA"):
        for record in raw.get(record_type, []):
            ip_val = _record_value(record)
            ip_entity = find_entity(EntityType.IP, ip_val)
            if ip_entity:
                add_rel(
                    domain_entity.id,
                    RelationshipType.HOSTED_ON,
                    ip_entity.id,
                    f"dns_{record_type.lower()}_record",
                    0.95,
                    evidence,
                )

    # NS → uses_nameserver
    for record in raw.get("NS", []):
        ns_val = _record_value(record)
        ns_entity = find_entity(EntityType.DOMAIN, ns_val)
        if ns_entity:
            add_rel(
                domain_entity.id,
                RelationshipType.USES_NAMESERVER,
                ns_entity.id,
                "dns_ns_record",
                0.95,
                evidence,
            )

    # MX → sends_mail_via
    for record in raw.get("MX", []):
        mx_val = (
            record.get("exchange", _record_value(record))
            if isinstance(record, dict)
            else str(record)
        )
        mx_entity = find_entity(EntityType.DOMAIN, mx_val)
        if mx_entity:
            add_rel(
                domain_entity.id,
                RelationshipType.SENDS_MAIL_VIA,
                mx_entity.id,
                "dns_mx_record",
                0.9,
                evidence,
            )


def _process_whois_relationships(
    target: str,
    raw: dict[str, Any],
    find_entity: Any,
    add_rel: Any,
    obs_id: str,
) -> None:
    """Process WHOIS data for relationships."""
    from app.services.normalizer import normalize_domain

    domain = normalize_domain(target)
    domain_entity = find_entity(EntityType.DOMAIN, domain)
    if not domain_entity:
        return

    evidence = [obs_id] if obs_id else []

    # Registrant email → registered_by
    registrant_email = raw.get("registrant_email", "")
    if registrant_email and registrant_email.lower() not in (
        "redacted",
        "privacy",
        "whoisguard",
    ):
        email_entity = find_entity(EntityType.EMAIL, registrant_email)
        if email_entity:
            add_rel(
                domain_entity.id,
                RelationshipType.REGISTERED_BY,
                email_entity.id,
                "whois_registrant_email",
                0.8,
                evidence,
            )

    # Registrar → registered_with
    registrar = raw.get("registrar", "")
    if registrar:
        reg_entity = find_entity(EntityType.ORGANIZATION, registrar)
        if reg_entity:
            add_rel(
                domain_entity.id,
                RelationshipType.REGISTERED_WITH,
                reg_entity.id,
                "whois_registrar",
                0.85,
                evidence,
            )

    # Nameservers → uses_nameserver
    nameservers = raw.get("nameservers", [])
    if isinstance(nameservers, str):
        nameservers = [nameservers]
    for ns in nameservers:
        if ns and ns.lower() not in ("redacted", "privacy"):
            ns_entity = find_entity(EntityType.DOMAIN, ns)
            if ns_entity:
                add_rel(
                    domain_entity.id,
                    RelationshipType.USES_NAMESERVER,
                    ns_entity.id,
                    "whois_nameserver",
                    0.9,
                    evidence,
                )


def _process_ct_relationships(
    target: str,
    raw: dict[str, Any],
    find_entity: Any,
    add_rel: Any,
    obs_id: str,
) -> None:
    """Process Certificate Transparency data for relationships."""
    from app.services.normalizer import normalize_domain

    domain = normalize_domain(target)
    domain_entity = find_entity(EntityType.DOMAIN, domain)
    if not domain_entity:
        return

    evidence = [obs_id] if obs_id else []

    for cert in raw.get("certificates", []):
        if not isinstance(cert, dict):
            continue

        cert_id = cert.get("id") or cert.get("issuer_name", "unknown")
        cert_entity = find_entity(EntityType.CERTIFICATE, str(cert_id))
        if cert_entity:
            add_rel(
                domain_entity.id,
                RelationshipType.COVERED_BY_CERTIFICATE,
                cert_entity.id,
                "ct_certificate",
                0.9,
                evidence,
            )

        # Issuer → issued_by
        issuer_name = cert.get("issuer_name", "")
        if issuer_name and cert_entity:
            issuer_org = _extract_issuer_org(issuer_name)
            if issuer_org:
                org_entity = find_entity(EntityType.ORGANIZATION, issuer_org)
                if org_entity:
                    add_rel(
                        cert_entity.id,
                        RelationshipType.ISSUED_BY,
                        org_entity.id,
                        "ct_issuer",
                        0.85,
                        evidence,
                    )

        # SANs → has_subdomain or covered_by_certificate
        name_value = cert.get("name_value", "")
        if name_value:
            for name in name_value.split("\n"):
                name = name.strip().lower()
                if name and name != domain and name.endswith(f".{domain}"):
                    sub_entity = find_entity(EntityType.SUBDOMAIN, name)
                    if sub_entity:
                        add_rel(
                            domain_entity.id,
                            RelationshipType.HAS_SUBDOMAIN,
                            sub_entity.id,
                            "ct_san",
                            0.9,
                            evidence,
                        )


def _process_ip_asn_relationships(
    target: str,
    raw: dict[str, Any],
    find_entity: Any,
    add_rel: Any,
    obs_id: str,
) -> None:
    """Process IP-to-ASN data for relationships."""
    from app.services.normalizer import normalize_ip

    ip = normalize_ip(target)
    ip_entity = find_entity(EntityType.IP, ip)
    if not ip_entity:
        return

    evidence = [obs_id] if obs_id else []

    # ASN → belongs_to_asn (canonical AS<number> form, matching extraction)
    asn_raw = str(raw.get("asn", "") or "").strip().upper()
    if asn_raw.startswith("AS"):
        asn_raw = asn_raw[2:].strip()
    asn = f"AS{asn_raw}" if asn_raw.isdigit() else ""
    if asn:
        asn_entity = find_entity(EntityType.ASN, asn)
        if asn_entity:
            add_rel(
                ip_entity.id,
                RelationshipType.BELONGS_TO_ASN,
                asn_entity.id,
                "ip_to_asn",
                0.9,
                evidence,
            )

    # Organization → operated_by
    org = raw.get("organization", "")
    if org:
        org_entity = find_entity(EntityType.ORGANIZATION, org)
        if org_entity:
            add_rel(
                ip_entity.id,
                RelationshipType.OPERATED_BY,
                org_entity.id,
                "ip_to_asn",
                0.8,
                evidence,
            )


def _process_http_relationships(
    target: str,
    raw: dict[str, Any],
    find_entity: Any,
    add_rel: Any,
    obs_id: str,
) -> None:
    """Process HTTP analysis data for technology relationships."""
    from app.services.normalizer import normalize_domain

    # Extract domain from URL
    domain = normalize_domain(target)
    domain_entity = find_entity(EntityType.DOMAIN, domain)
    if not domain_entity:
        return

    evidence = [obs_id] if obs_id else []

    # Technologies detected
    technologies = raw.get("technologies", [])
    if isinstance(technologies, list):
        for tech in technologies:
            tech_name = tech if isinstance(tech, str) else str(tech)
            tech_entity = find_entity(EntityType.TECHNOLOGY, tech_name)
            if tech_entity:
                add_rel(
                    domain_entity.id,
                    RelationshipType.USES_TECHNOLOGY,
                    tech_entity.id,
                    "http_tech_detection",
                    0.85,
                    evidence,
                )

    # Redirects → links_to
    redirects = raw.get("redirects", [])
    if isinstance(redirects, list):
        for redirect in redirects:
            redirect_url = redirect.get("url", "") if isinstance(redirect, dict) else str(redirect)
            if redirect_url:
                url_entity = find_entity(EntityType.URL, redirect_url)
                if url_entity:
                    add_rel(
                        domain_entity.id,
                        RelationshipType.LINKS_TO,
                        url_entity.id,
                        "http_redirect",
                        0.8,
                        evidence,
                    )


def _process_threat_relationships(
    target: str,
    raw: dict[str, Any],
    find_entity: Any,
    add_rel: Any,
    obs_id: str,
) -> None:
    """Process threat intelligence data for threat relationships."""
    # Determine if target is IP or domain
    from app.services.normalizer import is_valid_ip, normalize_domain, normalize_ip

    if is_valid_ip(target):
        entity = find_entity(EntityType.IP, normalize_ip(target))
    else:
        entity = find_entity(EntityType.DOMAIN, normalize_domain(target))

    if not entity:
        return

    evidence = [obs_id] if obs_id else []

    # AbuseIPDB score
    abuse_score = raw.get("abuse_score", 0)
    if abuse_score and abuse_score > 50:
        threat_entity = find_entity(EntityType.THREAT_INDICATOR, f"abuse_score_{abuse_score}")
        if not threat_entity:
            # Create inline
            threat_entity = ExtractedEntity(
                id=f"{EntityType.THREAT_INDICATOR.value.lower()}:abuse_score_{abuse_score}",
                entity_type=EntityType.THREAT_INDICATOR,
                value=f"AbuseIPDB score: {abuse_score}/100",
                confidence=0.85,
                sources=["threat_intel"],
                evidence_ids=[obs_id] if obs_id else [],
            )
        add_rel(
            entity.id,
            RelationshipType.ASSOCIATED_WITH_THREAT,
            threat_entity.id,
            "threat_intel_abuseipdb",
            0.85,
            evidence,
        )

    # URLhaus reports
    urlhaus = raw.get("urlhaus", {})
    if isinstance(urlhaus, dict) and urlhaus.get("threat"):
        threat_val = urlhaus["threat"]
        threat_entity = find_entity(EntityType.THREAT_INDICATOR, f"urlhaus_{threat_val}")
        if not threat_entity:
            threat_entity = ExtractedEntity(
                id=f"{EntityType.THREAT_INDICATOR.value.lower()}:urlhaus_{threat_val}",
                entity_type=EntityType.THREAT_INDICATOR,
                value=f"URLhaus: {threat_val}",
                confidence=0.8,
                sources=["threat_intel"],
                evidence_ids=[obs_id] if obs_id else [],
            )
        add_rel(
            entity.id,
            RelationshipType.ASSOCIATED_WITH_THREAT,
            threat_entity.id,
            "threat_intel_urlhaus",
            0.8,
            evidence,
        )


def _process_github_relationships(
    target: str,
    raw: dict[str, Any],
    find_entity: Any,
    add_rel: Any,
    obs_id: str,
) -> None:
    """Process GitHub API data for username/repo relationships."""
    from app.services.normalizer import normalize_email

    username = raw.get("login", target)
    username_entity = find_entity(EntityType.USERNAME, username)
    if not username_entity:
        return

    evidence = [obs_id] if obs_id else []

    # Email
    email = raw.get("email", "")
    if email:
        email_entity = find_entity(EntityType.EMAIL, normalize_email(email))
        if email_entity:
            add_rel(
                username_entity.id,
                RelationshipType.ASSOCIATED_WITH_EMAIL,
                email_entity.id,
                "github_profile",
                0.8,
                evidence,
            )

    # Organization
    org = raw.get("organization", "")
    if org:
        org_entity = find_entity(EntityType.ORGANIZATION, org)
        if org_entity:
            add_rel(
                username_entity.id,
                RelationshipType.MEMBER_OF,
                org_entity.id,
                "github_profile",
                0.75,
                evidence,
            )

    # Repositories
    repos = raw.get("repositories", [])
    if isinstance(repos, list):
        for repo in repos:
            repo_name = repo.get("name", "") if isinstance(repo, dict) else str(repo)
            if repo_name:
                repo_entity = find_entity(EntityType.REPOSITORY, repo_name)
                if repo_entity:
                    add_rel(
                        username_entity.id,
                        RelationshipType.OWNS_REPOSITORY,
                        repo_entity.id,
                        "github_repos",
                        0.85,
                        evidence,
                    )


def _extract_issuer_org(issuer_name: str) -> str | None:
    """Extract organization name from certificate issuer DN."""
    for part in issuer_name.split(","):
        part = part.strip()
        if part.upper().startswith("O="):
            return part[2:].strip()
    for part in issuer_name.split(","):
        part = part.strip()
        if part.upper().startswith("CN="):
            return part[3:].strip()
    return None
