"""AI analyzer — summarize findings, risk assessment, key findings.

Task 6.11: Use LLM to analyze investigation state and produce a summary,
risk assessment, and key findings. Output is advisory only and never
becomes source evidence.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.ai.validator import (
    validate_analyzer_output,
    validate_entity_ids,
)
from app.models.ai import AIAnalyzerOutput

logger = logging.getLogger(__name__)


def build_analyzer_prompt(
    investigation_target: str,
    target_type: str,
    graph_summary: dict[str, Any],
    pivot_rounds_completed: int,
) -> list[dict[str, str]]:
    """Build the LLM prompt messages for the AI analyzer.

    Args:
        investigation_target: The investigation target.
        target_type: Type of the target.
        graph_summary: Summary of the knowledge graph state.
        pivot_rounds_completed: Number of pivot rounds completed.

    Returns:
        List of message dicts for the LLM API call.
    """
    system_msg = (
        "You are an OSINT analysis assistant. Given the state of an investigation, "
        "provide an analysis with a summary, risk assessment, key findings, and "
        "recommendations.\n\n"
        "You MUST respond with valid JSON matching this schema:\n"
        "{\n"
        '  "summary": "<string: 2-5 sentence executive summary>",\n'
        '  "risk_level": "<one of: low, medium, high, critical>",\n'
        '  "risk_reasoning": "<string: why this risk level>",\n'
        '  "key_findings": [\n'
        "    {\n"
        '      "title": "<string: brief title>",\n'
        '      "description": "<string: detailed description>",\n'
        '      "entity_ids": [<list of entity IDs this finding relates to>],\n'
        '      "confidence": <float 0.0-1.0>\n'
        "    }\n"
        "  ],\n"
        '  "recommendations": [<list of recommended next steps>]\n'
        "}\n\n"
        "Rules:\n"
        "- Be objective and evidence-based.\n"
        "- Only reference entities that appear in the provided context.\n"
        "- Risk assessment should consider: threat indicators, exposure, "
        "data completeness, and potential impact.\n"
        "- Keep findings actionable and specific.\n"
        "- Return at most 10 key findings.\n"
        "- Return at most 5 recommendations."
    )

    entity_summary = graph_summary.get("entity_summary", [])
    relationship_summary = graph_summary.get("relationship_summary", [])
    entity_count = graph_summary.get("entity_count", 0)
    relationship_count = graph_summary.get("relationship_count", 0)

    user_parts = [
        f"Investigation target: {investigation_target}",
        f"Target type: {target_type}",
        f"Pivot rounds completed: {pivot_rounds_completed}",
        f"\nEntities discovered ({entity_count}):",
    ]

    for ent in entity_summary[:40]:
        user_parts.append(
            f"  - {ent.get('type', '?')}:{ent.get('value', '?')} "
            f"(confidence: {ent.get('confidence', 0):.2f})"
        )

    if entity_count > 40:
        user_parts.append(f"  ... and {entity_count - 40} more")

    user_parts.append(f"\nRelationships ({relationship_count}):")
    for rel in relationship_summary[:25]:
        user_parts.append(
            f"  - {rel.get('source', '?')} --[{rel.get('type', '?')}]--> "
            f"{rel.get('target', '?')}"
        )

    # Include threat indicators if present.
    threats = [
        e for e in entity_summary if e.get("type") == "ThreatIndicator"
    ]
    if threats:
        user_parts.append(f"\nThreat indicators found ({len(threats)}):")
        for t in threats:
            user_parts.append(f"  - {t.get('value', '?')}")

    user_parts.append(
        "\nBased on this data, provide your analysis. "
        "Focus on actionable intelligence and risk assessment."
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def parse_analyzer_response(response_text: str) -> AIAnalyzerOutput | None:
    """Parse and validate the LLM analyzer response.

    Args:
        response_text: Raw text response from the LLM.

    Returns:
        Validated AIAnalyzerOutput or None if parsing/validation fails.
    """
    text = response_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse AI analyzer response as JSON: %s", exc)
        return None

    return validate_analyzer_output(data)


async def analyze_investigation(
    *,
    investigation_id: str,
    target: str,
    target_type: str,
    graph_summary: dict[str, Any],
    pivot_rounds_completed: int,
    llm_call_fn: Any = None,
) -> AIAnalyzerOutput:
    """Analyze an investigation using AI with full validation.

    If no LLM call function is provided, returns a minimal safe result.

    Args:
        investigation_id: Investigation UUID.
        target: Investigation target.
        target_type: Target type string.
        graph_summary: Current graph state summary.
        pivot_rounds_completed: Number of pivot rounds completed.
        llm_call_fn: Async callable that takes messages and returns response text.

    Returns:
        Validated and sanitized AIAnalyzerOutput.
    """
    if llm_call_fn is None:
        logger.info("No LLM function provided, returning minimal analyzer output")
        return AIAnalyzerOutput(
            summary="AI analyzer not configured. Manual analysis recommended.",
            risk_level="low",
            risk_reasoning="No AI analysis performed",
        )

    messages = build_analyzer_prompt(
        investigation_target=target,
        target_type=target_type,
        graph_summary=graph_summary,
        pivot_rounds_completed=pivot_rounds_completed,
    )

    try:
        response_text = await llm_call_fn(messages)
    except Exception as exc:
        logger.error("LLM call failed during analysis: %s", exc)
        return AIAnalyzerOutput(
            summary=f"Analysis failed: {exc}",
            risk_level="low",
            risk_reasoning="LLM unavailable",
        )

    output = parse_analyzer_response(response_text)
    if output is None:
        return AIAnalyzerOutput(
            summary="Failed to parse AI analysis response",
            risk_level="low",
            risk_reasoning="Invalid AI output",
        )

    # Validate entity_ids in key findings against the database.
    all_entity_ids = set()
    for finding in output.key_findings:
        all_entity_ids.update(finding.entity_ids)

    if all_entity_ids:
        valid_ids = await validate_entity_ids(list(all_entity_ids), investigation_id)
        valid_set = set(valid_ids)
        for finding in output.key_findings:
            finding.entity_ids = [eid for eid in finding.entity_ids if eid in valid_set]

    # Limit output size.
    output.key_findings = output.key_findings[:10]
    output.recommendations = output.recommendations[:5]

    return output
