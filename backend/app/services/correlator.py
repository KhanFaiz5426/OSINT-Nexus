"""Correlation engine — orchestrates the full processing pipeline.

Task 5.7: Orchestrate normalize → extract → resolve → detect → write to graph.

This service connects the Phase 4 processing pipeline (normalizer, extractor,
resolver, relationship_detector, confidence scorer) to the Phase 5 graph
storage layer (Neo4j writer).

The correlator does NOT replace or duplicate deterministic Phase 4 logic.
It orchestrates existing services and persists results to the graph.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.graph.client import get_driver
from app.graph.writer import write_graph
from app.models.processing import ExtractedEntity, ExtractedRelationship
from app.services.confidence import score_all
from app.services.extractor import (
    extract_entities_from_text,
    extract_from_ct,
    extract_from_dns,
    extract_from_whois,
    extract_technologies_from_headers,
)
from app.services.relationship_detector import detect_relationships
from app.services.resolver import resolve_entities

logger = logging.getLogger(__name__)


async def correlate_observations(
    investigation_id: str,
    observations: list[dict[str, Any]],
    *,
    write_to_graph: bool = True,
) -> dict[str, Any]:
    """Run the full correlation pipeline on collected observations.

    Pipeline:
        observations → extract → resolve → detect relationships →
        score confidence → write to Neo4j

    Args:
        investigation_id: Owning investigation UUID.
        observations: List of observation dicts from PostgreSQL. Each has:
            - id: observation UUID
            - source_adapter: collector name
            - target: original target
            - raw_response: dict with raw collector data
        write_to_graph: Whether to write results to Neo4j (default True).

    Returns:
        Summary dict with counts and entity/relationship lists.
    """
    logger.info(
        "Starting correlation for investigation %s with %d observations",
        investigation_id,
        len(observations),
    )

    # Step 1: Extract entities from each observation.
    all_entities: dict[str, ExtractedEntity] = {}
    all_raw_results: list[dict[str, Any]] = []

    for obs in observations:
        obs_id = str(obs.get("id", ""))
        collector = obs.get("source_adapter", "")
        target = obs.get("target", "")
        raw_response = obs.get("raw_response", {})

        if not raw_response:
            continue

        # Extract entities based on collector type.
        entities, _ = _extract_from_observation(
            collector, target, raw_response, observation_id=obs_id
        )

        # Fix for email targets: explicitly inject Email entity
        from app.services.classifier import classify_target
        from app.models import TargetType, EntityType
        from app.services.normalizer import normalize_email
        
        if classify_target(target) == TargetType.EMAIL:
            email_val = normalize_email(target)
            email_id = f"{EntityType.EMAIL.value.lower()}:{email_val}"
            
            # Ensure email entity exists
            if not any(e.id == email_id for e in entities):
                entities.append(
                    ExtractedEntity(
                        id=email_id,
                        entity_type=EntityType.EMAIL,
                        value=email_val,
                        confidence=1.0,
                        first_seen=datetime.now(UTC),
                        last_seen=datetime.now(UTC),
                        sources=[collector],
                        evidence_ids=[obs_id] if obs_id else [],
                    )
                )

        for entity in entities:
            if entity.id in all_entities:
                existing = all_entities[entity.id]
                existing.touch(obs_id, collector)
                if entity.confidence > existing.confidence:
                    existing.confidence = entity.confidence
            else:
                all_entities[entity.id] = entity

        # Collect raw results for relationship detection.
        all_raw_results.append(
            {
                "collector_name": collector,
                "target": target,
                "raw_response": raw_response,
                "observation_id": obs_id,
            }
        )

    entity_list = list(all_entities.values())

    # Step 2: Resolve entities (deduplicate).
    resolved_entities, co_occurrence_rels = resolve_entities(
        entity_list, observations=observations
    )

    # Step 3: Detect relationships from raw collector data.
    structural_rels = detect_relationships(
        resolved_entities,
        all_raw_results,
        investigation_id=investigation_id,
    )

    # Merge structural and co-occurrence relationships.
    all_relationships = _merge_relationships(structural_rels, co_occurrence_rels)

    # Step 4: Score confidence for all entities and relationships.
    scored_entities, scored_relationships = score_all(
        resolved_entities, all_relationships
    )

    # Step 5: Write to Neo4j.
    nodes_written = 0
    edges_written = 0
    if write_to_graph and (scored_entities or scored_relationships):
        try:
            driver = await get_driver()
            nodes_written, edges_written = await write_graph(
                scored_entities,
                scored_relationships,
                investigation_id=investigation_id,
                driver=driver,
            )
        except Exception:
            logger.exception(
                "Failed to write graph for investigation %s", investigation_id
            )

    logger.info(
        "Correlation complete for %s: %d entities, %d relationships "
        "(%d nodes, %d edges written to graph)",
        investigation_id,
        len(scored_entities),
        len(scored_relationships),
        nodes_written,
        edges_written,
    )

    return {
        "investigation_id": investigation_id,
        "observations_processed": len(observations),
        "entities_extracted": len(entity_list),
        "entities_resolved": len(resolved_entities),
        "relationships_detected": len(all_relationships),
        "nodes_written": nodes_written,
        "edges_written": edges_written,
        "entities": scored_entities,
        "relationships": scored_relationships,
    }


def _extract_from_observation(
    collector: str,
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Dispatch extraction based on collector type."""
    if collector == "dns":
        return extract_from_dns(
            target, raw_response, observation_id=observation_id
        )
    elif collector == "whois":
        return extract_from_whois(
            target, raw_response, observation_id=observation_id
        )
    elif collector == "certificate_transparency":
        return extract_from_ct(
            target, raw_response, observation_id=observation_id
        )
    elif collector == "http":
        return _extract_from_http(target, raw_response, observation_id=observation_id)
    elif collector == "github":
        return _extract_from_github(target, raw_response, observation_id=observation_id)
    elif collector == "reddit":
        return _extract_from_reddit(target, raw_response, observation_id=observation_id)
    elif collector == "keybase":
        return _extract_from_keybase(target, raw_response, observation_id=observation_id)
    elif collector == "hackernews":
        return _extract_from_hackernews(target, raw_response, observation_id=observation_id)
    elif collector == "gitlab":
        return _extract_from_gitlab(target, raw_response, observation_id=observation_id)
    elif collector == "ip_to_asn":
        return _extract_from_ip_asn(target, raw_response, observation_id=observation_id)
    elif collector == "threat_intel":
        return _extract_from_threat_intel(target, raw_response, observation_id=observation_id)
    elif collector == "search":
        return _extract_from_search(target, raw_response, observation_id=observation_id)
    else:
        # Generic text extraction as fallback.
        return _extract_generic(target, raw_response, observation_id=observation_id), []


def _extract_from_http(
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Extract entities from HTTP collector output."""
    entities: list[ExtractedEntity] = []
    source = "http"

    # Extract technologies from headers.
    headers = raw_response.get("headers", {})
    if isinstance(headers, dict):
        tech_entities = extract_technologies_from_headers(
            headers, source=source, evidence_id=observation_id
        )
        entities.extend(tech_entities)

    # Extract entities from page title and content.
    title = raw_response.get("title", "")
    if title:
        text_entities = extract_entities_from_text(
            title, source=source, evidence_id=observation_id
        )
        entities.extend(text_entities)

    return entities, []


def _extract_from_github(
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Extract entities from GitHub collector output."""
    from app.models import EntityType
    from app.services.normalizer import normalize_email

    entities: list[ExtractedEntity] = []
    source = "github"
    now = datetime.now(UTC)

    # Profile → Username entity.
    login = raw_response.get("login", target)
    entities.append(
        ExtractedEntity(
            id=f"{EntityType.USERNAME.value.lower()}:{login}",
            entity_type=EntityType.USERNAME,
            value=login,
            confidence=0.9,
            first_seen=now,
            last_seen=now,
            sources=[source],
            evidence_ids=[observation_id] if observation_id else [],
        )
    )

    # Email.
    email = raw_response.get("email", "")
    if email:
        norm_email = normalize_email(email)
        entities.append(
            ExtractedEntity(
                id=f"{EntityType.EMAIL.value.lower()}:{norm_email}",
                entity_type=EntityType.EMAIL,
                value=norm_email,
                confidence=0.8,
                first_seen=now,
                last_seen=now,
                sources=[source],
                evidence_ids=[observation_id] if observation_id else [],
            )
        )

    # Organization.
    org = raw_response.get("organization", "")
    if org:
        entities.append(
            ExtractedEntity(
                id=f"{EntityType.ORGANIZATION.value.lower()}:{org}",
                entity_type=EntityType.ORGANIZATION,
                value=org,
                confidence=0.75,
                first_seen=now,
                last_seen=now,
                sources=[source],
                evidence_ids=[observation_id] if observation_id else [],
            )
        )

    # Repositories.
    repos = raw_response.get("repositories", [])
    if isinstance(repos, list):
        for repo in repos:
            repo_name = repo.get("name", "") if isinstance(repo, dict) else str(repo)
            if repo_name:
                entities.append(
                    ExtractedEntity(
                        id=f"{EntityType.REPOSITORY.value.lower()}:{repo_name}",
                        entity_type=EntityType.REPOSITORY,
                        value=repo_name,
                        confidence=0.85,
                        first_seen=now,
                        last_seen=now,
                        sources=[source],
                        evidence_ids=[observation_id] if observation_id else [],
                    )
                )

    return entities, []


def _extract_from_ip_asn(
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Extract entities from IP-to-ASN collector output."""
    from app.models import EntityType
    from app.services.normalizer import normalize_ip

    entities: list[ExtractedEntity] = []
    source = "ip_to_asn"
    now = datetime.now(UTC)

    # IP entity.
    ip_val = normalize_ip(target)
    entities.append(
        ExtractedEntity(
            id=f"{EntityType.IP.value.lower()}:{ip_val}",
            entity_type=EntityType.IP,
            value=ip_val,
            confidence=0.9,
            first_seen=now,
            last_seen=now,
            sources=[source],
            evidence_ids=[observation_id] if observation_id else [],
        )
    )

    # ASN entity.
    asn = raw_response.get("asn", "")
    if asn:
        entities.append(
            ExtractedEntity(
                id=f"{EntityType.ASN.value.lower()}:{asn}",
                entity_type=EntityType.ASN,
                value=asn,
                confidence=0.88,
                first_seen=now,
                last_seen=now,
                sources=[source],
                evidence_ids=[observation_id] if observation_id else [],
            )
        )

    # Organization.
    org = raw_response.get("organization", "")
    if org:
        entities.append(
            ExtractedEntity(
                id=f"{EntityType.ORGANIZATION.value.lower()}:{org}",
                entity_type=EntityType.ORGANIZATION,
                value=org,
                confidence=0.8,
                first_seen=now,
                last_seen=now,
                sources=[source],
                evidence_ids=[observation_id] if observation_id else [],
            )
        )

    return entities, []


def _extract_from_threat_intel(
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Extract entities from threat intelligence collector output."""
    from app.models import EntityType
    from app.services.normalizer import is_valid_ip, normalize_domain, normalize_ip

    entities: list[ExtractedEntity] = []
    source = "threat_intel"
    now = datetime.now(UTC)

    # Target entity (IP or domain).
    if is_valid_ip(target):
        norm_val = normalize_ip(target)
        etype = EntityType.IP
    else:
        norm_val = normalize_domain(target)
        etype = EntityType.DOMAIN

    entities.append(
        ExtractedEntity(
            id=f"{etype.value.lower()}:{norm_val}",
            entity_type=etype,
            value=norm_val,
            confidence=0.85,
            first_seen=now,
            last_seen=now,
            sources=[source],
            evidence_ids=[observation_id] if observation_id else [],
        )
    )

    # Threat indicator from AbuseIPDB.
    abuse_score = raw_response.get("abuse_score", 0)
    if abuse_score and abuse_score > 50:
        entities.append(
            ExtractedEntity(
                id=f"{EntityType.THREAT_INDICATOR.value.lower()}:abuse_score_{abuse_score}",
                entity_type=EntityType.THREAT_INDICATOR,
                value=f"AbuseIPDB score: {abuse_score}/100",
                confidence=0.85,
                first_seen=now,
                last_seen=now,
                sources=[source],
                evidence_ids=[observation_id] if observation_id else [],
            )
        )

    return entities, []


def _extract_from_search(
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Extract entities from search collector output.

    The search collector returns extracted_entities with domains, emails,
    URLs, and IPs discovered in search result snippets.
    """
    from app.models import EntityType
    from app.services.normalizer import normalize_domain, normalize_email, normalize_ip

    entities: list[ExtractedEntity] = []
    relationships: list[ExtractedRelationship] = []
    source = "search"
    now = datetime.now(UTC)

    extracted = raw_response.get("extracted_entities", {})

    # Extract domains found in search results
    for domain in extracted.get("domains", []):
        norm_domain = normalize_domain(domain)
        if norm_domain:
            entities.append(
                ExtractedEntity(
                    id=f"{EntityType.DOMAIN.value.lower()}:{norm_domain}",
                    entity_type=EntityType.DOMAIN,
                    value=norm_domain,
                    confidence=0.7,
                    first_seen=now,
                    last_seen=now,
                    sources=[source],
                    evidence_ids=[observation_id] if observation_id else [],
                )
            )

    # Extract emails found in search results
    for email in extracted.get("emails", []):
        norm_email = normalize_email(email)
        if norm_email:
            entities.append(
                ExtractedEntity(
                    id=f"{EntityType.EMAIL.value.lower()}:{norm_email}",
                    entity_type=EntityType.EMAIL,
                    value=norm_email,
                    confidence=0.6,
                    first_seen=now,
                    last_seen=now,
                    sources=[source],
                    evidence_ids=[observation_id] if observation_id else [],
                )
            )

    # Extract IPs found in search results
    for ip in extracted.get("ips", []):
        norm_ip = normalize_ip(ip)
        if norm_ip:
            entities.append(
                ExtractedEntity(
                    id=f"{EntityType.IP.value.lower()}:{norm_ip}",
                    entity_type=EntityType.IP,
                    value=norm_ip,
                    confidence=0.6,
                    first_seen=now,
                    last_seen=now,
                    sources=[source],
                    evidence_ids=[observation_id] if observation_id else [],
                )
            )

    # Create a search result entity linking the target to what was found
    result_count = raw_response.get("result_count", 0)
    if result_count > 0:
        search_query = raw_response.get("query", target)
        entities.append(
            ExtractedEntity(
                id=f"search_result:{target}:{search_query}",
                entity_type=EntityType.DOMAIN,  # Use Domain as the closest type
                value=f"Search results for: {search_query}",
                confidence=0.5,
                first_seen=now,
                last_seen=now,
                sources=[source],
                evidence_ids=[observation_id] if observation_id else [],
            )
        )

    return entities, relationships


def _extract_generic(
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
) -> list[ExtractedEntity]:
    """Generic entity extraction from any raw response."""
    import json

    # Flatten the response to text for regex extraction.
    text = json.dumps(raw_response, default=str)
    return extract_entities_from_text(
        text, source="generic", evidence_id=observation_id
    )


def _extract_from_reddit(
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Extract entities from Reddit collector output."""
    from app.models import EntityType

    entities: list[ExtractedEntity] = []
    source = "reddit"
    now = datetime.now(UTC)

    profile = raw_response.get("profile", {})
    if not profile or not raw_response.get("found"):
        return entities, []

    # Username entity.
    username = profile.get("name", target)
    entities.append(
        ExtractedEntity(
            id=f"{EntityType.USERNAME.value.lower()}:{username}",
            entity_type=EntityType.USERNAME,
            value=username,
            confidence=0.9,
            first_seen=now,
            last_seen=now,
            sources=[source],
            evidence_ids=[observation_id] if observation_id else [],
        )
    )

    return entities, []


def _extract_from_keybase(
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Extract entities from Keybase collector output."""
    from app.models import EntityType
    from app.services.normalizer import normalize_email

    entities: list[ExtractedEntity] = []
    source = "keybase"
    now = datetime.now(UTC)

    profile = raw_response.get("profile", {})
    if not profile or not raw_response.get("found"):
        return entities, []

    # Username entity.
    username = profile.get("username", target)
    entities.append(
        ExtractedEntity(
            id=f"{EntityType.USERNAME.value.lower()}:{username}",
            entity_type=EntityType.USERNAME,
            value=username,
            confidence=0.9,
            first_seen=now,
            last_seen=now,
            sources=[source],
            evidence_ids=[observation_id] if observation_id else [],
        )
    )

    # Full name → PERSON entity.
    full_name = profile.get("full_name", "")
    if full_name:
        entities.append(
            ExtractedEntity(
                id=f"{EntityType.PERSON.value.lower()}:{full_name}",
                entity_type=EntityType.PERSON,
                value=full_name,
                confidence=0.7,
                first_seen=now,
                last_seen=now,
                sources=[source],
                evidence_ids=[observation_id] if observation_id else [],
            )
        )

    # Social proofs → USERNAME entities on other platforms.
    for proof in profile.get("social_proofs", []):
        service = proof.get("service", "")
        proof_username = proof.get("username", "")
        if service and proof_username:
            entities.append(
                ExtractedEntity(
                    id=f"{EntityType.USERNAME.value.lower()}:{proof_username}",
                    entity_type=EntityType.USERNAME,
                    value=proof_username,
                    confidence=0.85,
                    first_seen=now,
                    last_seen=now,
                    sources=[source],
                    evidence_ids=[observation_id] if observation_id else [],
                )
            )

    # Website → URL entity.
    website = profile.get("website", "")
    if website:
        entities.append(
            ExtractedEntity(
                id=f"{EntityType.URL.value.lower()}:{website}",
                entity_type=EntityType.URL,
                value=website,
                confidence=0.6,
                first_seen=now,
                last_seen=now,
                sources=[source],
                evidence_ids=[observation_id] if observation_id else [],
            )
        )

    return entities, []


def _extract_from_hackernews(
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Extract entities from HackerNews collector output."""
    from app.models import EntityType

    entities: list[ExtractedEntity] = []
    source = "hackernews"
    now = datetime.now(UTC)

    profile = raw_response.get("profile", {})
    if not profile or not raw_response.get("found"):
        return entities, []

    # Username entity.
    username = profile.get("username", target)
    entities.append(
        ExtractedEntity(
            id=f"{EntityType.USERNAME.value.lower()}:{username}",
            entity_type=EntityType.USERNAME,
            value=username,
            confidence=0.9,
            first_seen=now,
            last_seen=now,
            sources=[source],
            evidence_ids=[observation_id] if observation_id else [],
        )
    )

    return entities, []


def _extract_from_gitlab(
    target: str,
    raw_response: dict[str, Any],
    *,
    observation_id: str = "",
) -> tuple[list[ExtractedEntity], list[ExtractedRelationship]]:
    """Extract entities from GitLab collector output."""
    from app.models import EntityType
    from app.services.normalizer import normalize_email

    entities: list[ExtractedEntity] = []
    source = "gitlab"
    now = datetime.now(UTC)

    profile = raw_response.get("profile", {})
    if not profile or not raw_response.get("found"):
        return entities, []

    # Username entity.
    username = profile.get("username", target)
    entities.append(
        ExtractedEntity(
            id=f"{EntityType.USERNAME.value.lower()}:{username}",
            entity_type=EntityType.USERNAME,
            value=username,
            confidence=0.9,
            first_seen=now,
            last_seen=now,
            sources=[source],
            evidence_ids=[observation_id] if observation_id else [],
        )
    )

    # Email entity.
    email = profile.get("email", "")
    if email:
        norm_email = normalize_email(email)
        entities.append(
            ExtractedEntity(
                id=f"{EntityType.EMAIL.value.lower()}:{norm_email}",
                entity_type=EntityType.EMAIL,
                value=norm_email,
                confidence=0.8,
                first_seen=now,
                last_seen=now,
                sources=[source],
                evidence_ids=[observation_id] if observation_id else [],
            )
        )

    # Organization entity.
    org = profile.get("organization", "")
    if org:
        entities.append(
            ExtractedEntity(
                id=f"{EntityType.ORGANIZATION.value.lower()}:{org}",
                entity_type=EntityType.ORGANIZATION,
                value=org,
                confidence=0.75,
                first_seen=now,
                last_seen=now,
                sources=[source],
                evidence_ids=[observation_id] if observation_id else [],
            )
        )

    # Projects → REPOSITORY entities.
    for project in raw_response.get("projects", []):
        project_path = project.get("path", "")
        if project_path:
            entities.append(
                ExtractedEntity(
                    id=f"{EntityType.REPOSITORY.value.lower()}:{project_path}",
                    entity_type=EntityType.REPOSITORY,
                    value=project_path,
                    confidence=0.85,
                    first_seen=now,
                    last_seen=now,
                    sources=[source],
                    evidence_ids=[observation_id] if observation_id else [],
                )
            )

    # Groups → ORGANIZATION entities.
    for group in raw_response.get("groups", []):
        group_path = group.get("path", "")
        if group_path:
            entities.append(
                ExtractedEntity(
                    id=f"{EntityType.ORGANIZATION.value.lower()}:{group_path}",
                    entity_type=EntityType.ORGANIZATION,
                    value=group_path,
                    confidence=0.7,
                    first_seen=now,
                    last_seen=now,
                    sources=[source],
                    evidence_ids=[observation_id] if observation_id else [],
                )
            )

    return entities, []


def _merge_relationships(
    structural: list[ExtractedRelationship],
    co_occurrence: list[ExtractedRelationship],
) -> list[ExtractedRelationship]:
    """Merge relationship lists, deduplicating by ID."""
    seen: dict[str, ExtractedRelationship] = {}

    for rel in structural:
        if rel.id not in seen:
            seen[rel.id] = rel
        else:
            # Merge evidence.
            existing = seen[rel.id]
            for eid in rel.evidence_ids:
                if eid not in existing.evidence_ids:
                    existing.evidence_ids.append(eid)
            if rel.confidence > existing.confidence:
                existing.confidence = rel.confidence

    for rel in co_occurrence:
        if rel.id not in seen:
            seen[rel.id] = rel
        else:
            existing = seen[rel.id]
            for eid in rel.evidence_ids:
                if eid not in existing.evidence_ids:
                    existing.evidence_ids.append(eid)
            if rel.confidence > existing.confidence:
                existing.confidence = rel.confidence

    return list(seen.values())
