"""Investigation orchestrator — automated collection loop.

Tasks 6.1-6.5: Dispatch initial collectors, run the collect → normalize →
extract → resolve → correlate pipeline, track budget and depth, enforce
stopping conditions.

The orchestrator is deterministic. It calls the AI planner for advice
but makes all dispatch decisions independently.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.ai.analyzer import analyze_investigation
from app.ai.planner import (
    DEPTH_MAX_ROUNDS,
    plan_pivots_with_ai,
    select_initial_actions,
)
from app.collectors.registry import get_collector, initialize_collectors
from app.db.client import get_pool
from app.graph.reader import get_investigation_subgraph
from app.models import (
    InvestigationDepth,
    InvestigationStatus,
    RawResult,
    TargetType,
)
from app.models.ai import PivotAction, PivotRecommendation
from app.services.classifier import classify_target
from app.services.correlator import correlate_observations
from app.services.pivot_selector import ACTION_TO_COLLECTOR, select_pivots

logger = logging.getLogger(__name__)


# ── Budget and depth constants ────────────────────────────────────────────────

MAX_PIVOTS_PER_ROUND = 5
DEFAULT_BUDGET = 100
DEPTH_MAX_ROUNDS_MAP = DEPTH_MAX_ROUNDS


# ── Investigation state tracking ─────────────────────────────────────────────


class InvestigationState:
    """Tracks the mutable state of a running investigation.

    Budget and depth are enforced independently of the LLM.
    """

    def __init__(
        self,
        investigation_id: str,
        target: str,
        target_type: TargetType,
        depth: InvestigationDepth,
        budget: int,
    ) -> None:
        self.investigation_id = investigation_id
        self.target = target
        self.target_type = target_type
        self.depth = depth
        self.budget_remaining = budget
        self.current_round = 0
        self.max_rounds = DEPTH_MAX_ROUNDS_MAP.get(depth, 3)
        self.dispatched_targets: set[str] = {target.strip().lower()}
        self.recent_action_counts: dict[str, int] = {}
        self.total_pivots_dispatched = 0
        self.total_observations_collected = 0
        self.stopped = False
        self.stop_reason = ""

    @property
    def budget_exhausted(self) -> bool:
        return self.budget_remaining <= 0

    @property
    def depth_reached(self) -> bool:
        return self.current_round >= self.max_rounds

    def consume_budget(self, amount: int = 1) -> None:
        self.budget_remaining = max(0, self.budget_remaining - amount)

    def record_dispatch(self, action: PivotAction, target: str) -> None:
        self.dispatched_targets.add(target.strip().lower())
        self.recent_action_counts[action.value] = (
            self.recent_action_counts.get(action.value, 0) + 1
        )
        self.total_pivots_dispatched += 1

    def next_round(self) -> None:
        self.current_round += 1
        self.recent_action_counts.clear()

    def check_stopping_conditions(self) -> str | None:
        """Check if the investigation should stop.

        Returns:
            Stop reason string, or None if investigation should continue.
        """
        if self.budget_exhausted:
            return "budget_exhausted"
        if self.depth_reached:
            return "depth_reached"
        return None


# ── Collector dispatch ────────────────────────────────────────────────────────


def action_to_collector_name(action: PivotAction) -> str:
    """Map a PivotAction to the collector name."""
    return ACTION_TO_COLLECTOR.get(action, "")


async def dispatch_collector(
    action: PivotAction,
    target: str,
    target_type: TargetType,
    investigation_id: str,
) -> RawResult | None:
    """Dispatch a single collector action synchronously.

    Executes the collector and returns the raw result. Does NOT store
    the observation — that happens in the collect→process pipeline.

    Args:
        action: The collector action to dispatch.
        target: The target to collect on.
        target_type: Type of the target.
        investigation_id: Investigation UUID.

    Returns:
        RawResult from the collector, or None on failure.
    """
    collector_name = action_to_collector_name(action)
    if not collector_name:
        logger.warning("Unknown action: %s", action.value)
        return None

    collector = get_collector(collector_name)
    if collector is None:
        logger.warning("Collector not registered: %s", collector_name)
        return None

    try:
        result = await collector.collect(target, target_type=target_type)
        return result
    except Exception as exc:
        logger.error("Collector %s failed for %s: %s", collector_name, target, exc)
        return None


async def collect_and_store(
    action: PivotAction,
    target: str,
    target_type: TargetType,
    investigation_id: str,
) -> dict[str, Any] | None:
    """Collect data and store the observation to PostgreSQL.

    Returns the stored observation dict, or None on failure.
    """
    result = await dispatch_collector(action, target, target_type, investigation_id)
    if result is None:
        return None

    # Store observation.
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO observations
                    (investigation_id, source_adapter, source_version, collected_at,
                     method, target, raw_response, normalized_value, confidence, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id::text
                """,
                investigation_id,
                result.collector_name,
                result.collector_version,
                result.collected_at,
                result.query,
                result.target,
                json.dumps(result.raw_response),
                result.normalized_value,
                result.confidence,
                result.status.value,
            )
            return {
                "id": row["id"],
                "source_adapter": result.collector_name,
                "target": result.target,
                "raw_response": result.raw_response,
                "status": result.status.value,
            }
    except Exception as exc:
        logger.error("Failed to store observation for %s/%s: %s", action.value, target, exc)
        return None


# ── Graph summary for AI ─────────────────────────────────────────────────────


async def get_graph_summary(investigation_id: str) -> dict[str, Any]:
    """Build a summary of the knowledge graph for AI consumption.

    Returns a lightweight dict with entity/relationship summaries.
    """
    try:
        graph = await get_investigation_subgraph(investigation_id)
    except Exception:
        logger.debug("Could not fetch graph for summary, using empty")
        return {
            "entity_count": 0,
            "relationship_count": 0,
            "entity_summary": [],
            "relationship_summary": [],
        }

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    entity_summary = []
    for node in nodes:
        data = node.get("data", {})
        entity_summary.append({
            "type": data.get("type", "Unknown"),
            "value": data.get("label", ""),
            "confidence": data.get("confidence", 0.0),
            "source_count": data.get("source_count", 0),
            "id": data.get("id", ""),
        })

    relationship_summary = []
    for edge in edges:
        data = edge.get("data", {})
        relationship_summary.append({
            "source": data.get("source", ""),
            "target": data.get("target", ""),
            "type": data.get("relationship_type", ""),
            "confidence": data.get("confidence", 0.0),
        })

    return {
        "entity_count": len(entity_summary),
        "relationship_count": len(relationship_summary),
        "entity_summary": entity_summary,
        "relationship_summary": relationship_summary,
    }


# ── Activity log ─────────────────────────────────────────────────────────────


async def log_activity(
    investigation_id: str,
    event_type: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Write an event to the investigation activity log."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO activity_log (investigation_id, event_type, details)
                VALUES ($1, $2, $3)
                """,
                investigation_id,
                event_type,
                json.dumps(details or {}),
            )
    except Exception as exc:
        logger.warning("Failed to log activity: %s", exc)


# ── Investigation status updates ─────────────────────────────────────────────


async def update_investigation_status(
    investigation_id: str,
    status: InvestigationStatus,
    *,
    extra_fields: dict[str, Any] | None = None,
) -> None:
    """Update investigation status and optionally other fields."""
    pool = await get_pool()
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        if extra_fields:
            set_clauses = ["status = $1", "updated_at = $2"]
            params: list[Any] = [status.value, now]
            for i, (key, val) in enumerate(extra_fields.items(), start=3):
                set_clauses.append(f"{key} = ${i}")
                params.append(val)
            params.append(investigation_id)
            await conn.execute(
                f"UPDATE investigations SET {', '.join(set_clauses)} WHERE id = ${len(params)}",
                *params,
            )
        else:
            await conn.execute(
                "UPDATE investigations SET status = $1, updated_at = $2 WHERE id = $3",
                status.value,
                now,
                investigation_id,
            )


async def increment_api_calls(investigation_id: str, count: int = 1) -> None:
    """Increment the API calls used counter for the investigation."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE investigations
                SET api_calls_used = api_calls_used + $1, updated_at = $2
                WHERE id = $3
                """,
                count,
                datetime.now(UTC),
                investigation_id,
            )
    except Exception as exc:
        logger.warning("Failed to increment API calls: %s", exc)


# ── Main orchestration loop ──────────────────────────────────────────────────


async def run_investigation_loop(
    investigation_id: str,
    *,
    llm_call_fn: Any = None,
    stop_event: asyncio.Event | None = None,
) -> dict[str, Any]:
    """Run the full investigation loop.

    Pipeline: collect → normalize → extract → resolve → correlate →
    AI plans → pivot → collect → ... → stop

    Budget, depth, and stopping conditions are enforced independently
    of the LLM.

    Args:
        investigation_id: Investigation UUID.
        llm_call_fn: Optional async callable for LLM interaction.
        stop_event: Optional asyncio.Event to signal external stop.

    Returns:
        Summary dict with investigation results.
    """
    logger.info("Starting investigation loop for %s", investigation_id)

    # Load investigation state from DB.
    state = await _load_investigation_state(investigation_id)
    if state is None:
        logger.error("Investigation %s not found", investigation_id)
        return {"error": "Investigation not found"}

    # Initialize collectors if needed.
    from app.collectors.cache import CollectorCache
    from app.collectors.registry import get_all_collectors
    from app.core.redis import get_redis

    if not get_all_collectors():
        try:
            redis_client = await get_redis()
            cache = CollectorCache(redis_client)
            await initialize_collectors(cache=cache)
        except Exception:
            await initialize_collectors(cache=None)

    # Set status to running.
    await update_investigation_status(investigation_id, InvestigationStatus.RUNNING)
    await log_activity(investigation_id, "investigation_started", {
        "target": state.target,
        "target_type": state.target_type.value,
        "depth": state.depth.value,
        "budget": state.budget_remaining,
    })

    try:
        # Phase 1: Initial collection based on target type.
        initial_actions = select_initial_actions(state.target_type)
        initial_observations = await _dispatch_initial_collectors(
            state, initial_actions
        )

        # Phase 1b: Correlate initial observations.
        if initial_observations:
            await correlate_observations(investigation_id, initial_observations)
            await increment_api_calls(investigation_id, len(initial_observations))

        # Phase 2: AI-guided pivot loop.
        while True:
            # Check stopping conditions.
            stop_reason = state.check_stopping_conditions()
            if stop_reason:
                state.stopped = True
                state.stop_reason = stop_reason
                logger.info("Investigation %s stopping: %s", investigation_id, stop_reason)
                break

            # Check external stop signal.
            if stop_event and stop_event.is_set():
                state.stopped = True
                state.stop_reason = "external_stop"
                break

            # Get graph summary for AI.
            graph_summary = await get_graph_summary(investigation_id)

            # If no new entities discovered in this round, stop.
            if (
                state.current_round > 0
                and graph_summary.get("entity_count", 0) == 0
            ):
                state.stopped = True
                state.stop_reason = "no_new_entities"
                logger.info("Investigation %s stopping: no new entities", investigation_id)
                break

            # Get recent pivots for context.
            recent_pivots = await _get_recent_pivots(investigation_id)

            # AI planning.
            planner_output = await plan_pivots_with_ai(
                investigation_id=investigation_id,
                target=state.target,
                target_type=state.target_type,
                current_round=state.current_round,
                max_rounds=state.max_rounds,
                graph_summary=graph_summary,
                budget_remaining=state.budget_remaining,
                recent_pivots=recent_pivots,
                llm_call_fn=llm_call_fn,
            )

            # Check if AI recommends stop.
            if planner_output.stop_recommended:
                state.stopped = True
                state.stop_reason = planner_output.stop_reason or "ai_recommended_stop"
                await log_activity(investigation_id, "ai_recommended_stop", {
                    "reason": planner_output.stop_reason,
                })
                break

            # Deterministic pivot selection (filtered by constraints).
            pivots = select_pivots(
                planner_output,
                budget_remaining=state.budget_remaining,
                dispatched_targets=state.dispatched_targets,
                recent_action_counts=state.recent_action_counts,
            )

            if not pivots:
                state.stopped = True
                state.stop_reason = "no_valid_pivots"
                logger.info("Investigation %s stopping: no valid pivots", investigation_id)
                break

            # Dispatch pivots.
            round_observations = await _dispatch_pivots(state, pivots)

            # Correlate round observations.
            if round_observations:
                await correlate_observations(investigation_id, round_observations)
                await increment_api_calls(investigation_id, len(round_observations))

            # Move to next round.
            state.next_round()

            await log_activity(investigation_id, "pivot_round_completed", {
                "round": state.current_round,
                "pivots_dispatched": len(pivots),
                "observations_collected": len(round_observations),
                "budget_remaining": state.budget_remaining,
                "entity_count": graph_summary.get("entity_count", 0),
            })

        # Phase 3: AI analysis of final state.
        graph_summary = await get_graph_summary(investigation_id)
        analyzer_output = await analyze_investigation(
            investigation_id=investigation_id,
            target=state.target,
            target_type=state.target_type.value,
            graph_summary=graph_summary,
            pivot_rounds_completed=state.current_round,
            llm_call_fn=llm_call_fn,
        )

        # Final status update.
        final_status = (
            InvestigationStatus.STOPPED
            if state.stop_reason in ("external_stop", "budget_exhausted", "depth_reached")
            else InvestigationStatus.COMPLETED
        )
        await update_investigation_status(
            investigation_id,
            final_status,
            extra_fields={"api_calls_used": DEFAULT_BUDGET - state.budget_remaining},
        )

        await log_activity(investigation_id, "investigation_completed", {
            "status": final_status.value,
            "stop_reason": state.stop_reason,
            "total_rounds": state.current_round,
            "total_pivots_dispatched": state.total_pivots_dispatched,
            "budget_remaining": state.budget_remaining,
        })

        result = {
            "investigation_id": investigation_id,
            "status": final_status.value,
            "stop_reason": state.stop_reason,
            "total_rounds": state.current_round,
            "total_pivots_dispatched": state.total_pivots_dispatched,
            "budget_remaining": state.budget_remaining,
            "graph_summary": graph_summary,
            "analyzer_output": analyzer_output.model_dump() if analyzer_output else None,
        }

        logger.info("Investigation %s completed: %s", investigation_id, state.stop_reason)
        return result

    except Exception as exc:
        logger.exception("Investigation %s failed: %s", investigation_id, exc)
        await update_investigation_status(
            investigation_id, InvestigationStatus.ERROR
        )
        await log_activity(investigation_id, "investigation_error", {"error": str(exc)})
        return {"error": str(exc), "investigation_id": investigation_id}


# ── Helper functions ─────────────────────────────────────────────────────────


async def _load_investigation_state(
    investigation_id: str,
) -> InvestigationState | None:
    """Load investigation data from DB and create state object."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, target, target_type, depth, status, api_calls_used, api_budget
            FROM investigations
            WHERE id = $1
            """,
            investigation_id,
        )

    if row is None:
        return None

    status = row["status"]
    if status not in (InvestigationStatus.CREATED.value, InvestigationStatus.RUNNING.value):
        return None

    budget_used = row["api_calls_used"]
    budget_total = row["api_budget"]
    budget_remaining = max(0, budget_total - budget_used)

    return InvestigationState(
        investigation_id=str(row["id"]),
        target=row["target"],
        target_type=TargetType(row["target_type"]),
        depth=InvestigationDepth(row["depth"]),
        budget=budget_remaining,
    )


async def _dispatch_initial_collectors(
    state: InvestigationState,
    actions: list[PivotAction],
) -> list[dict[str, Any]]:
    """Dispatch initial collectors for the investigation target."""
    observations: list[dict[str, Any]] = []

    for action in actions:
        if state.budget_exhausted:
            break

        obs = await collect_and_store(
            action, state.target, state.target_type, state.investigation_id
        )
        if obs is not None:
            observations.append(obs)
            state.consume_budget()
            state.record_dispatch(action, state.target)

    return observations


async def _dispatch_pivots(
    state: InvestigationState,
    pivots: list[PivotRecommendation],
) -> list[dict[str, Any]]:
    """Dispatch pivot recommendations."""
    observations: list[dict[str, Any]] = []

    for pivot in pivots:
        if state.budget_exhausted:
            break

        # Classify the pivot target type.
        pivot_target_type = classify_target(pivot.target)

        obs = await collect_and_store(
            pivot.action,
            pivot.target,
            pivot_target_type,
            state.investigation_id,
        )
        if obs is not None:
            observations.append(obs)
            state.consume_budget()
            state.record_dispatch(pivot.action, pivot.target)

    return observations


async def _get_recent_pivots(investigation_id: str) -> list[dict[str, Any]]:
    """Get recent pivot actions from the activity log."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT details, created_at
                FROM activity_log
                WHERE investigation_id = $1
                  AND event_type = 'pivot_dispatched'
                ORDER BY created_at DESC
                LIMIT 10
                """,
                investigation_id,
            )
        return [
            {
                "target": dict(r["details"]).get("target", ""),
                "action": dict(r["details"]).get("action", ""),
            }
            for r in rows
        ]
    except Exception:
        return []
