"""Pydantic models for AI planner and analyzer structured output.

These models define strict schemas for LLM-generated JSON. All AI output
is validated against these schemas before use. The LLM is advisory only;
deterministic code remains authoritative.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ── Planner output models ────────────────────────────────────────────────────


class PivotAction(StrEnum):
    """Permitted collector actions for pivots."""

    COLLECT_DNS = "collect_dns"
    COLLECT_WHOIS = "collect_whois"
    COLLECT_CT = "collect_ct"
    COLLECT_IP_ASN = "collect_ip_asn"
    COLLECT_GITHUB = "collect_github"
    COLLECT_HTTP = "collect_http"
    COLLECT_THREAT_INTEL = "collect_threat_intel"
    COLLECT_REDDIT = "collect_reddit"
    COLLECT_KEYBASE = "collect_keybase"
    COLLECT_HACKERNEWS = "collect_hackernews"
    COLLECT_GITLAB = "collect_gitlab"
    COLLECT_SEARCH = "collect_search"


class PivotRecommendation(BaseModel):
    """A single pivot recommendation from the AI planner."""

    target: str = Field(
        ..., min_length=1, max_length=500, description="The target to investigate next"
    )
    action: PivotAction = Field(..., description="The collector action to dispatch")
    reasoning: str = Field(
        default="",
        max_length=2000,
        description="LLM reasoning for this recommendation",
    )
    priority: int = Field(default=5, ge=1, le=10, description="Priority (1=highest, 10=lowest)")
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Observation IDs the AI based this recommendation on",
    )


class AIPlannerOutput(BaseModel):
    """Structured output from the AI planner LLM call.

    Validated strictly before any dispatch.
    """

    pivots: list[PivotRecommendation] = Field(
        default_factory=list,
        max_length=10,
        description="Recommended pivots, ordered by priority",
    )
    summary: str = Field(
        default="",
        max_length=3000,
        description="Brief reasoning summary for this planning step",
    )
    stop_recommended: bool = Field(
        default=False,
        description="Whether the AI recommends stopping the investigation",
    )
    stop_reason: str = Field(
        default="",
        max_length=1000,
        description="Reason for recommending stop",
    )

    @field_validator("stop_reason", mode="before")
    @classmethod
    def coerce_stop_reason(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)

    @field_validator("summary", mode="before")
    @classmethod
    def coerce_summary(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)


# ── Analyzer output models ───────────────────────────────────────────────────


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class KeyFinding(BaseModel):
    """A single key finding from the AI analyzer."""

    title: str = Field(..., max_length=200, description="Brief title of the finding")
    description: str = Field(..., max_length=2000, description="Detailed description")
    entity_ids: list[str] = Field(
        default_factory=list,
        description="Entity IDs relevant to this finding",
    )
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="AI confidence in this finding"
    )


class AIAnalyzerOutput(BaseModel):
    """Structured output from the AI analyzer LLM call.

    Validated strictly before storage. Never treated as source evidence.
    """

    summary: str = Field(default="", max_length=5000, description="Executive summary of findings")
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="Overall risk assessment")
    risk_reasoning: str = Field(
        default="", max_length=3000, description="Reasoning for risk assessment"
    )
    key_findings: list[KeyFinding] = Field(
        default_factory=list,
        max_length=20,
        description="Key findings from the investigation",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Recommended next steps",
    )


# ── API response models ──────────────────────────────────────────────────────


class AIAnalysisResponse(BaseModel):
    """Response model for the AI analysis API endpoint."""

    investigation_id: str
    planner_output: AIPlannerOutput | None = None
    analyzer_output: AIAnalyzerOutput | None = None
    generated_at: str = ""
    pivot_rounds_completed: int = 0
    total_pivots_dispatched: int = 0
