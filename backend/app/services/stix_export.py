"""STIX 2.1 Export — convert OSINT entities to STIX 2.1 format.

Exports investigation data as a STIX 2.1 Bundle for integration with
threat intelligence platforms (MISP, OpenCTI, etc.).
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid5

from app.models import EntityType

logger = logging.getLogger(__name__)

# STIX 2.1 namespace for generating deterministic IDs
STIX_NAMESPACE = "d895aa52-df85-4cfb-8306-cf80b54a2c3e"

# Mapping from OSINT entity types to STIX 2.1 SDO types
ENTITY_TYPE_TO_STIX: dict[EntityType, str] = {
    EntityType.DOMAIN: "domain-name",
    EntityType.IP: "ipv4-addr",
    EntityType.EMAIL: "email-addr",
    EntityType.URL: "url",
    EntityType.ORGANIZATION: "identity",
    EntityType.PERSON: "identity",
    EntityType.USERNAME: "identity",
    EntityType.REPOSITORY: "software",
    EntityType.ASN: "autonomous-system",
    EntityType.THREAT_INDICATOR: "indicator",
    EntityType.CERTIFICATE: "x509-certificate",
    EntityType.TECHNOLOGY: "software",
    EntityType.SUBDOMAIN: "domain-name",
}

# Mapping from relationship types to STIX SRO types
REL_TYPE_TO_STIX: dict[str, str] = {
    "hosted_on": "communicates-with",
    "uses_nameserver": "resolves-to",
    "sends_mail_via": "communicates-with",
    "registered_by": "attributed-to",
    "has_subdomain": "has",
    "belongs_to_asn": "located-at",
    "associated_with_email": "attributed-to",
    "associated_with_threat": "indicates",
    "co_occurs_with": "related-to",
    "same_person": "related-to",
}


def generate_stix_id(stix_type: str, value: str) -> str:
    """Generate a deterministic STIX 2.1 ID."""
    return f"{stix_type}--{uuid5(STIX_NAMESPACE, f'{stix_type}:{value}')}"


def entity_to_stix(entity: dict[str, Any], investigation_id: str) -> dict[str, Any]:
    """Convert an OSINT entity to a STIX 2.1 SDO."""
    entity_type_str = entity.get("type", "Domain")
    value = entity.get("value", "")

    # Map entity type
    try:
        entity_type = EntityType(entity_type_str)
    except ValueError:
        entity_type = EntityType.DOMAIN

    stix_type = ENTITY_TYPE_TO_STIX.get(entity_type, "x-osint-entity")
    stix_id = generate_stix_id(stix_type, f"{investigation_id}:{value}")

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # Build base SDO
    sdo: dict[str, Any] = {
        "type": stix_type,
        "spec_version": "2.1",
        "id": stix_id,
        "created": now,
        "modified": now,
    }

    # Type-specific fields
    if (
        stix_type == "domain-name"
        or stix_type == "ipv4-addr"
        or stix_type == "email-addr"
        or stix_type == "url"
    ):
        sdo["value"] = value

    elif stix_type == "identity":
        sdo["name"] = value
        sdo["identity_class"] = "individual" if entity_type == EntityType.PERSON else "organization"

    elif stix_type == "software":
        sdo["name"] = value

    elif stix_type == "autonomous-system":
        # Extract ASN number from value like "AS12345"
        asn_num = 0
        if value.upper().startswith("AS"):
            with contextlib.suppress(ValueError):
                asn_num = int(value[2:])
        sdo["number"] = asn_num
        sdo["name"] = value

    elif stix_type == "indicator":
        # Create a STIX indicator from threat data
        sdo["pattern"] = f"[artifact:payload_bin = '{value}']"
        sdo["pattern_type"] = "stix"
        sdo["valid_from"] = now
        sdo["indicator_types"] = ["malicious-activity"]

    elif stix_type == "x509-certificate":
        sdo["serial_number"] = value

    else:
        # Generic entity
        sdo["name"] = value

    # Add confidence and description
    confidence = entity.get("confidence", 0.5)
    sdo["confidence"] = int(confidence * 100)
    sdo["description"] = f"OSINT Nexus entity: {entity_type_str}:{value}"

    # Add custom properties
    sdo["x_investigation_id"] = investigation_id
    sdo["x_source_count"] = entity.get("source_count", 1)

    return sdo


def relationship_to_stix(
    rel: dict[str, Any],
    investigation_id: str,
) -> dict[str, Any] | None:
    """Convert an OSINT relationship to a STIX 2.1 SRO."""
    rel_type = rel.get("relationship_type", "co_occurs_with")
    source_id = rel.get("source", "")
    target_id = rel.get("target", "")

    if not source_id or not target_id:
        return None

    stix_type = REL_TYPE_TO_STIX.get(rel_type, "related-to")
    stix_id = generate_stix_id(stix_type, f"{investigation_id}:{source_id}:{target_id}")

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    return {
        "type": stix_type,
        "spec_version": "2.1",
        "id": stix_id,
        "created": now,
        "modified": now,
        "relationship_type": stix_type,
        "source_ref": source_id,
        "target_ref": target_id,
        "confidence": int(rel.get("confidence", 0.5) * 100),
        "description": f"OSINT relationship: {rel_type}",
    }


def investigation_to_stix_bundle(
    investigation_data: dict[str, Any],
) -> dict[str, Any]:
    """Convert investigation export data to a STIX 2.1 Bundle.

    Args:
        investigation_data: Full investigation export dict from export_investigation().

    Returns:
        STIX 2.1 Bundle dict ready for JSON serialization.
    """
    objects: list[dict[str, Any]] = []
    investigation_id = investigation_data.get("investigation", {}).get("id", "")

    # Convert entities to STIX SDOs
    entity_stix_ids: dict[str, str] = {}
    for entity in investigation_data.get("entities", []):
        stix_sdo = entity_to_stix(entity, investigation_id)
        entity_stix_ids[entity.get("id", "")] = stix_sdo["id"]
        objects.append(stix_sdo)

    # Convert relationships to STIX SROs
    for rel in investigation_data.get("graph", {}).get("edges", []):
        data = rel.get("data", rel)
        # Map source/target IDs to STIX IDs
        data_copy = dict(data)
        data_copy["source"] = entity_stix_ids.get(data.get("source", ""), data.get("source", ""))
        data_copy["target"] = entity_stix_ids.get(data.get("target", ""), data.get("target", ""))

        stix_sro = relationship_to_stix(data_copy, investigation_id)
        if stix_sro:
            objects.append(stix_sro)

    # Create the bundle
    datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    bundle = {
        "type": "bundle",
        "id": f"bundle--{uuid5(STIX_NAMESPACE, f'bundle:{investigation_id}')}",
        "spec_version": "2.1",
        "objects": objects,
    }

    logger.info(
        "Generated STIX 2.1 bundle for investigation %s: %d objects",
        investigation_id,
        len(objects),
    )

    return bundle
