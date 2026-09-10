"""OSINT Nexus Backend — Pydantic Models."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ── Enums ────────────────────────────────────────────────────────────────────


class TargetType(StrEnum):
    DOMAIN = "domain"
    IP = "ip"
    URL = "url"
    EMAIL = "email"
    USERNAME = "username"
    ORGANIZATION = "organization"
    UNKNOWN = "unknown"


class InvestigationStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ERROR = "error"


class InvestigationDepth(StrEnum):
    SHALLOW = "shallow"
    STANDARD = "standard"
    DEEP = "deep"


class ObservationStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class EntityType(StrEnum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    DOMAIN = "Domain"
    SUBDOMAIN = "Subdomain"
    IP = "IP"
    ASN = "ASN"
    CERTIFICATE = "Certificate"
    URL = "URL"
    EMAIL = "Email"
    USERNAME = "Username"
    REPOSITORY = "Repository"
    TECHNOLOGY = "Technology"
    THREAT_INDICATOR = "ThreatIndicator"


class SourceAvailabilityStatus(StrEnum):
    """Evidence-based source accessibility states."""

    AVAILABLE = "available"
    NOT_FOUND = "not_found"
    REDIRECTED = "redirected"
    ACCESS_DENIED = "access_denied"
    AUTH_REQUIRED = "auth_required"
    RATE_LIMITED = "rate_limited"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class RelationshipType(StrEnum):
    HOSTED_ON = "hosted_on"
    USES_NAMESERVER = "uses_nameserver"
    SENDS_MAIL_VIA = "sends_mail_via"
    REGISTERED_BY = "registered_by"
    REGISTERED_WITH = "registered_with"
    HAS_SUBDOMAIN = "has_subdomain"
    COVERED_BY_CERTIFICATE = "covered_by_certificate"
    ISSUED_BY = "issued_by"
    BELONGS_TO_ASN = "belongs_to_asn"
    OPERATED_BY = "operated_by"
    HAS_PTR = "has_ptr"
    OWNS_REPOSITORY = "owns_repository"
    HAS_ACCOUNT_ON = "has_account_on"
    ASSOCIATED_WITH_EMAIL = "associated_with_email"
    MEMBER_OF = "member_of"
    USES_TECHNOLOGY = "uses_technology"
    LINKS_TO = "links_to"
    ASSOCIATED_WITH_THREAT = "associated_with_threat"
    CO_OCCURS_WITH = "co_occurs_with"
    SAME_PERSON = "same_person"
    HAS_EMAIL = "has_email"


# ── Request / Response Models ────────────────────────────────────────────────


class InvestigationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    target: str = Field(..., min_length=1, max_length=500)
    depth: InvestigationDepth = InvestigationDepth.STANDARD


class InvestigationResponse(BaseModel):
    id: str
    name: str
    target: str
    target_type: TargetType
    status: InvestigationStatus
    depth: InvestigationDepth
    created_at: datetime
    updated_at: datetime
    entity_count: int = 0
    relationship_count: int = 0
    observation_count: int = 0


class InvestigationDetail(InvestigationResponse):
    api_calls_used: int = 0
    api_budget: int = 100


class EntityResponse(BaseModel):
    id: str
    investigation_id: str
    type: EntityType
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    source_count: int = 0
    properties: dict[str, Any] = Field(default_factory=dict)


class RelationshipResponse(BaseModel):
    id: str
    source_entity_id: str
    target_entity_id: str
    type: RelationshipType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    discovered_at: datetime | None = None
    method: str = ""


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    total_nodes: int | None = None
    total_edges: int | None = None


class ReportResponse(BaseModel):
    id: str
    investigation_id: str
    format: str
    created_at: datetime
    download_url: str
    file_size: int = 0


class ReportGenerateRequest(BaseModel):
    format: str = Field(
        default="html",
        pattern="^(html|pdf|json|csv|stix)$",
        description="Report format: html, pdf, json, csv, or stix",
    )


class MessageResponse(BaseModel):
    message: str
    detail: str = ""


# ── Collector Models (Phase 3) ──────────────────────────────────────────────


class RawResult(BaseModel):
    """Standardized result from any OSINT collector.

    Every collector returns this model. Raw results are immutable once created.
    """

    collector_name: str = Field(..., description="Name of the collector adapter")
    collector_version: str = Field(default="1.0.0", description="Version of the collector")
    target: str = Field(..., description="The target that was queried")
    target_type: TargetType = Field(..., description="Type of the target")
    query: str = Field(default="", description="The specific query/method used")
    status: ObservationStatus = Field(
        default=ObservationStatus.SUCCESS, description="Outcome of the collection"
    )
    raw_response: dict[str, Any] = Field(
        default_factory=dict, description="Raw response data from the source"
    )
    normalized_value: str = Field(default="", description="Normalized representation")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in the result")
    error_message: str = Field(default="", description="Error details if status is not success")
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Timestamp of collection"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional collector-specific metadata"
    )


class CollectorHealth(BaseModel):
    """Health check result for a collector."""

    name: str
    version: str
    available: bool
    api_key_configured: bool = False
    rate_limit_rpm: int = 0
    cache_ttl_seconds: int = 0
    last_error: str = ""


# ── Manual Entity / Relationship Creation (Item 9) ─────────────────────────


class EntityCreate(BaseModel):
    """Request model for creating a manual entity."""

    entity_type: EntityType = Field(..., description="Type of entity to create")
    value: str = Field(..., min_length=1, max_length=500, description="Entity value")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score")
    properties: dict[str, Any] = Field(default_factory=dict, description="Additional properties")


class RelationshipCreate(BaseModel):
    """Request model for creating a manual relationship."""

    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    rel_type: RelationshipType = Field(..., description="Relationship type")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score")
    method: str = Field(default="manual", description="How this relationship was discovered")


class SourceAvailabilityResponse(BaseModel):
    """Source URL availability check result."""

    url: str
    status: SourceAvailabilityStatus
    checked_at: str
    detail: str
    final_url: str = ""
