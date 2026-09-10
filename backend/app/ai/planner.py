"""AI planner — LLM-based pivot planning with structured JSON output.

Task 6.9+6.10: Prompt LLM with graph state, get pivot recommendations
with reasoning. Parse and validate structured JSON output.

The planner is advisory only. Deterministic code validates all output
and controls actual dispatch. The LLM never executes tools directly.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.ai.validator import validate_observation_ids, validate_planner_output
from app.models import EntityType, InvestigationDepth, TargetType
from app.models.ai import AIPlannerOutput, PivotAction

logger = logging.getLogger(__name__)

# Mapping from EntityType to the collector action that produces them.
_ENTITY_TO_COLLECTOR: dict[EntityType, PivotAction] = {
    EntityType.DOMAIN: PivotAction.COLLECT_DNS,
    EntityType.SUBDOMAIN: PivotAction.COLLECT_DNS,
    EntityType.IP: PivotAction.COLLECT_IP_ASN,
    EntityType.ASN: PivotAction.COLLECT_IP_ASN,
    EntityType.EMAIL: PivotAction.COLLECT_WHOIS,
    EntityType.URL: PivotAction.COLLECT_HTTP,
    EntityType.REPOSITORY: PivotAction.COLLECT_GITHUB,
    EntityType.USERNAME: PivotAction.COLLECT_GITHUB,
    EntityType.THREAT_INDICATOR: PivotAction.COLLECT_THREAT_INTEL,
    EntityType.CERTIFICATE: PivotAction.COLLECT_CT,
    EntityType.TECHNOLOGY: PivotAction.COLLECT_HTTP,
}

# Mapping from TargetType to initial collector actions.
TARGET_TYPE_INITIAL_ACTIONS: dict[TargetType, list[PivotAction]] = {
    TargetType.DOMAIN: [
        PivotAction.COLLECT_DNS,
        PivotAction.COLLECT_WHOIS,
        PivotAction.COLLECT_CT,
        PivotAction.COLLECT_HTTP,
        PivotAction.COLLECT_SEARCH,
    ],
    TargetType.IP: [
        PivotAction.COLLECT_DNS,
        PivotAction.COLLECT_IP_ASN,
        PivotAction.COLLECT_HTTP,
        PivotAction.COLLECT_THREAT_INTEL,
    ],
    TargetType.URL: [
        PivotAction.COLLECT_DNS,
        PivotAction.COLLECT_HTTP,
        PivotAction.COLLECT_SEARCH,
    ],
    TargetType.EMAIL: [
        PivotAction.COLLECT_GITHUB,
        PivotAction.COLLECT_DNS,
        PivotAction.COLLECT_WHOIS,
        PivotAction.COLLECT_HTTP,
    ],
    TargetType.USERNAME: [
        PivotAction.COLLECT_SEARCH,
    ],
    TargetType.ORGANIZATION: [
        PivotAction.COLLECT_GITHUB,
        PivotAction.COLLECT_DNS,
        PivotAction.COLLECT_SEARCH,
        PivotAction.COLLECT_HTTP,
        PivotAction.COLLECT_WHOIS,
    ],
    TargetType.UNKNOWN: [
        PivotAction.COLLECT_DNS,
        PivotAction.COLLECT_HTTP,
        PivotAction.COLLECT_SEARCH,
    ],
}

DEPTH_MAX_ROUNDS: dict[InvestigationDepth, int] = {
    InvestigationDepth.SHALLOW: 1,
    InvestigationDepth.STANDARD: 3,
    InvestigationDepth.DEEP: 6,
}


def build_planner_prompt(
    investigation_target: str,
    target_type: TargetType,
    current_round: int,
    max_rounds: int,
    graph_summary: dict[str, Any],
    budget_remaining: int,
    recent_pivots: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build the LLM prompt messages for the AI planner.

    Constructs a system + user message pair that describes the current
    investigation state and asks for pivot recommendations.

    Args:
        investigation_target: The original investigation target.
        target_type: Type of the target.
        current_round: Current pivot round (0-based).
        max_rounds: Maximum allowed pivot rounds.
        graph_summary: Summary of the current knowledge graph.
        budget_remaining: Remaining API budget.
        recent_pivots: Recent pivot actions taken.

    Returns:
        List of message dicts for the LLM API call.
    """
    system_msg = (
        "You are an OSINT investigation planner. Given the current state of an "
        "investigation, recommend the next set of pivots (collection actions) to "
        "expand the knowledge graph.\n\n"
        "You MUST respond with valid JSON matching this schema:\n"
        "{\n"
        '  "pivots": [\n'
        "    {\n"
        '      "target": "<string: target to investigate>",\n'
        '      "action": "<one of: collect_dns, collect_whois, collect_ct, '
        "collect_ip_asn, collect_github, collect_http, collect_threat_intel>\",\n"
        '      "reasoning": "<string: why this pivot is valuable>",\n'
        '      "priority": <int 1-10, 1=highest>,\n'
        '      "evidence_ids": [<list of observation IDs this is based on>]\n'
        "    }\n"
        "  ],\n"
        '  "summary": "<string: brief reasoning summary>",\n'
        '  "stop_recommended": <boolean>,\n'
        '  "stop_reason": "<string if stop_recommended is true>"\n'
        "}\n\n"
        "Rules:\n"
        "- Only recommend actions from the permitted list above.\n"
        "- Return at most 5 pivots.\n"
        "- Do NOT recommend pivots that have already been done.\n"
        "- If the investigation seems complete, set stop_recommended=true.\n"
        "- Keep reasoning concise and evidence-based.\n"
        "- Never reference entity or observation IDs that do not appear in the context."
    )

    entity_summary = graph_summary.get("entity_summary", [])
    relationship_summary = graph_summary.get("relationship_summary", [])
    entity_count = graph_summary.get("entity_count", 0)
    relationship_count = graph_summary.get("relationship_count", 0)

    user_parts = [
        f"Investigation target: {investigation_target}",
        f"Target type: {target_type.value}",
        f"Round: {current_round + 1} of {max_rounds}",
        f"Budget remaining: {budget_remaining} API calls",
        f"\nEntities discovered so far ({entity_count}):",
    ]

    for ent in entity_summary[:30]:
        user_parts.append(
            f"  - {ent.get('type', '?')}:{ent.get('value', '?')} "
            f"(confidence: {ent.get('confidence', 0):.2f}, "
            f"sources: {ent.get('source_count', 0)})"
        )

    if entity_count > 30:
        user_parts.append(f"  ... and {entity_count - 30} more")

    user_parts.append(f"\nRelationships discovered ({relationship_count}):")
    for rel in relationship_summary[:20]:
        user_parts.append(
            f"  - {rel.get('source', '?')} --[{rel.get('type', '?')}]--> "
            f"{rel.get('target', '?')} (confidence: {rel.get('confidence', 0):.2f})"
        )

    if recent_pivots:
        user_parts.append("\nRecent pivots already taken:")
        for p in recent_pivots[-10:]:
            user_parts.append(f"  - {p.get('action', '?')} on {p.get('target', '?')}")

    user_parts.append(
        "\nBased on this state, recommend the next pivots. "
        "Prioritize high-value targets that expand coverage."
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def parse_planner_response(response_text: str) -> AIPlannerOutput | None:
    """Parse and validate the LLM planner response.

    Extracts JSON from the response text (handles markdown code blocks),
    validates against the schema, and returns the parsed output.

    Args:
        response_text: Raw text response from the LLM.

    Returns:
        Validated AIPlannerOutput or None if parsing/validation fails.
    """
    from app.ai.response_parser import extract_json_from_llm_response

    data = extract_json_from_llm_response(response_text)
    if data is None:
        return None

    return validate_planner_output(data)


def select_initial_actions(
    target_type: TargetType,
) -> list[PivotAction]:
    """Select initial collector actions based on target type.

    This is deterministic and does not require the LLM.

    Args:
        target_type: Type of the investigation target.

    Returns:
        List of collector actions to dispatch.
    """
    return TARGET_TYPE_INITIAL_ACTIONS.get(
        target_type, TARGET_TYPE_INITIAL_ACTIONS[TargetType.UNKNOWN]
    )


async def plan_pivots_with_ai(
    *,
    investigation_id: str,
    target: str,
    target_type: TargetType,
    current_round: int,
    max_rounds: int,
    graph_summary: dict[str, Any],
    budget_remaining: int,
    recent_pivots: list[dict[str, Any]],
    llm_call_fn: Any = None,
) -> AIPlannerOutput:
    """Plan pivots using AI with full validation.

    If no LLM call function is provided, returns a safe empty result.
    All AI output is validated and hallucinated IDs are filtered.

    Args:
        investigation_id: Investigation UUID.
        target: Investigation target.
        target_type: Target type.
        current_round: Current pivot round.
        max_rounds: Maximum allowed rounds.
        graph_summary: Current graph state summary.
        budget_remaining: Remaining API budget.
        recent_pivots: Recent pivot actions.
        llm_call_fn: Async callable that takes messages and returns response text.
            Signature: async def fn(messages: list[dict]) -> str

    Returns:
        Validated and sanitized AIPlannerOutput.
    """
    if llm_call_fn is None:
        logger.info("No LLM function provided, returning empty planner output")
        return AIPlannerOutput(
            summary="AI planner not configured",
            stop_recommended=True,
            stop_reason="LLM not available",
        )

    messages = build_planner_prompt(
        investigation_target=target,
        target_type=target_type,
        current_round=current_round,
        max_rounds=max_rounds,
        graph_summary=graph_summary,
        budget_remaining=budget_remaining,
        recent_pivots=recent_pivots,
    )

    try:
        response_text = await llm_call_fn(messages)
        logger.debug("LLM planner response length: %d chars", len(response_text))
    except Exception as exc:
        logger.error(
            "LLM call failed during planning: %s: %s (investigation=%s, round=%d/%d)",
            type(exc).__name__, str(exc)[:300],
            investigation_id, current_round + 1, max_rounds,
        )
        # Don't recommend stop — let the deterministic pipeline decide
        # based on budget/depth. Returning empty pivots means this round
        # contributes nothing, but the investigation continues.
        return AIPlannerOutput(
            summary=f"LLM unavailable ({type(exc).__name__}); deterministic mode active",
            stop_recommended=True,
            stop_reason=f"LLM unavailable ({type(exc).__name__})",
        )

    output = parse_planner_response(response_text)
    if output is None:
        logger.warning("Failed to parse AI planner response, falling back to deterministic mode")
        return AIPlannerOutput(
            summary="Failed to parse AI planning response (invalid JSON); deterministic mode active",
            stop_recommended=False,
        )

    # Validate and sanitize evidence_ids in pivots.
    all_evidence_ids = set()
    for pivot in output.pivots:
        all_evidence_ids.update(pivot.evidence_ids)

    if all_evidence_ids:
        valid_ids = await validate_observation_ids(
            list(all_evidence_ids), investigation_id
        )
        valid_set = set(valid_ids)
        for pivot in output.pivots:
            pivot.evidence_ids = [
                eid for eid in pivot.evidence_ids if eid in valid_set
            ]

    # Limit to top 5 pivots.
    output.pivots = output.pivots[:5]

    return output
