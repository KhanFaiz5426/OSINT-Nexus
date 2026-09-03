"""Internal processing models for extracted entities and relationships.

These models represent the output of entity extraction, resolution,
and relationship detection — before storage in Neo4j.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models import EntityType, RelationshipType


class ExtractedEntity(BaseModel):
    """An entity extracted from OSINT collector data.

    Represents a single, normalized entity discovered during investigation.
    """

    id: str = Field(
        ...,
        description="Stable dedup key: '{type}:{normalized_value}'",
    )
    entity_type: EntityType
    value: str = Field(..., description="Canonical value")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    first_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sources: list[str] = Field(
        default_factory=list,
        description="Collector names that contributed this entity",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Observation IDs supporting this entity",
    )
    properties: dict[str, Any] = Field(default_factory=dict)

    def touch(self, observation_id: str = "", source: str = "") -> None:
        """Update last_seen and append new evidence."""
        self.last_seen = datetime.now(UTC)
        if observation_id and observation_id not in self.evidence_ids:
            self.evidence_ids.append(observation_id)
        if source and source not in self.sources:
            self.sources.append(source)


class ExtractedRelationship(BaseModel):
    """A relationship between two entities, detected during extraction."""

    id: str = Field(
        ...,
        description="Stable key: '{source_id}:{rel_type}:{target_id}'",
    )
    source_entity_id: str
    target_entity_id: str
    rel_type: RelationshipType
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    method: str = Field(
        default="",
        description="How this relationship was detected (e.g., 'dns_a_record')",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for graph storage."""
        return {
            "id": self.id,
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "type": self.rel_type.value,
            "confidence": self.confidence,
            "evidence_ids": self.evidence_ids,
            "discovered_at": self.discovered_at.isoformat(),
            "method": self.method,
        }
