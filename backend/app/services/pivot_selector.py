"""Pivot selector — filter AI recommendations by constraints.

Task 6.12: Filter pivot recommendations by budget, rate limits,
duplicates, and permitted collectors. Deterministic code remains
authoritative for all dispatch decisions.
"""

from __future__ import annotations

import logging

from app.models import TargetType
from app.models.ai import AIPlannerOutput, PivotAction, PivotRecommendation
from app.services.classifier import classify_target

logger = logging.getLogger(__name__)

# Mapping from PivotAction to the collector name in the registry.
ACTION_TO_COLLECTOR: dict[PivotAction, str] = {
    PivotAction.COLLECT_DNS: "dns",
    PivotAction.COLLECT_WHOIS: "whois",
    PivotAction.COLLECT_CT: "certificate_transparency",
    PivotAction.COLLECT_IP_ASN: "ip_to_asn",
    PivotAction.COLLECT_GITHUB: "github",
    PivotAction.COLLECT_HTTP: "http",
    PivotAction.COLLECT_THREAT_INTEL: "threat_intel",
    PivotAction.COLLECT_REDDIT: "reddit",
    PivotAction.COLLECT_KEYBASE: "keybase",
    PivotAction.COLLECT_HACKERNEWS: "hackernews",
    PivotAction.COLLECT_GITLAB: "gitlab",
    PivotAction.COLLECT_SEARCH: "search",
}


def filter_by_budget(
    pivots: list[PivotRecommendation],
    budget_remaining: int,
) -> list[PivotRecommendation]:
    """Remove pivots if budget is exhausted.

    Each pivot consumes at least 1 API call. If budget is 0, no pivots
    can be dispatched.

    Args:
        pivots: Candidate pivots.
        budget_remaining: Remaining API budget.

    Returns:
        Pivots that fit within the budget.
    """
    if budget_remaining <= 0:
        logger.info("Budget exhausted (%d remaining), rejecting all pivots", budget_remaining)
        return []
    # Each pivot costs at least 1 API call.
    return pivots[:budget_remaining]


def filter_by_permitted_collectors(
    pivots: list[PivotRecommendation],
    permitted_actions: set[PivotAction] | None = None,
) -> list[PivotRecommendation]:
    """Remove pivots that use non-permitted collector actions.

    Args:
        pivots: Candidate pivots.
        permitted_actions: Set of allowed actions. None = all permitted.

    Returns:
        Pivots using permitted actions only.
    """
    if permitted_actions is None:
        return pivots
    return [p for p in pivots if p.action in permitted_actions]


def filter_by_duplicates(
    pivots: list[PivotRecommendation],
    dispatched_targets: set[str],
) -> list[PivotRecommendation]:
    """Remove pivots for targets that have already been collected.

    Args:
        pivots: Candidate pivots.
        dispatched_targets: Set of target strings already dispatched.

    Returns:
        Pivots for new targets only.
    """
    seen = set(dispatched_targets)
    result = []
    for pivot in pivots:
        normalized = pivot.target.strip().lower()
        if normalized not in seen:
            seen.add(normalized)
            result.append(pivot)
    return result


def filter_by_rate_limits(
    pivots: list[PivotRecommendation],
    recent_action_counts: dict[str, int],
) -> list[PivotRecommendation]:
    """Filter pivots based on rate limit thresholds.

    Simple rate-limit check: reject a pivot if we've already dispatched
    more than 20 calls for that collector in the current round.

    Args:
        pivots: Candidate pivots.
        recent_action_counts: Map of action name -> count in current round.

    Returns:
        Pivots that are within rate limits.
    """
    rate_limit_per_round = 20
    result = []
    for pivot in pivots:
        count = recent_action_counts.get(pivot.action.value, 0)
        if count < rate_limit_per_round:
            result.append(pivot)
        else:
            logger.debug(
                "Rate limit reached for %s (%d this round), skipping pivot",
                pivot.action.value,
                count,
            )
    return result


def classify_pivot_target(target: str) -> TargetType:
    """Classify a pivot target's type.

    Uses the existing deterministic classifier.

    Args:
        target: The pivot target string.

    Returns:
        Classified TargetType.
    """
    return classify_target(target)


def select_pivots(
    planner_output: AIPlannerOutput,
    *,
    budget_remaining: int,
    dispatched_targets: set[str],
    recent_action_counts: dict[str, int],
    permitted_actions: set[PivotAction] | None = None,
) -> list[PivotRecommendation]:
    """Apply all filters to select valid pivots from AI recommendations.

    This is the main entry point for pivot selection. It applies filters
    in order: permitted collectors → duplicates → rate limits → budget.

    Args:
        planner_output: Validated AI planner output.
        budget_remaining: Remaining API budget.
        dispatched_targets: Targets already dispatched.
        recent_action_counts: Action counts for rate limiting.
        permitted_actions: Allowed collector actions (None = all).

    Returns:
        Filtered and ordered list of pivots ready for dispatch.
    """
    pivots = list(planner_output.pivots)

    # Sort by priority (lower = higher priority).
    pivots.sort(key=lambda p: p.priority)

    # Apply filters in sequence.
    pivots = filter_by_permitted_collectors(pivots, permitted_actions)
    pivots = filter_by_duplicates(pivots, dispatched_targets)
    pivots = filter_by_rate_limits(pivots, recent_action_counts)
    pivots = filter_by_budget(pivots, budget_remaining)

    logger.info(
        "Pivot selection: %d candidates → %d after filtering (budget=%d, dispatched=%d)",
        len(planner_output.pivots),
        len(pivots),
        budget_remaining,
        len(dispatched_targets),
    )

    return pivots
