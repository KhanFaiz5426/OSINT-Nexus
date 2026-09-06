"""AI validation tests — edge cases and safety scenarios.

Tests for malformed AI output, unsafe pivots, budget/depth edge cases,
and deterministic fallback behavior. Complements test_phase6_integration.py.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.ai import (
    AIAnalyzerOutput,
    AIPlannerOutput,
    PivotAction,
    PivotRecommendation,
    RiskLevel,
)
from app.services.pivot_selector import (
    filter_by_budget,
    filter_by_duplicates,
    filter_by_rate_limits,
    select_pivots,
)

# ── Malformed AI output tests ────────────────────────────────────────────────


class TestMalformedPlannerOutput:
    """Tests for handling malformed LLM planner responses."""

    def test_empty_json_object(self):
        """Empty JSON should produce default (empty) planner output."""
        output = AIPlannerOutput.model_validate({})
        assert output.pivots == []
        assert output.summary == ""
        assert output.stop_recommended is False

    def test_missing_pivots_key(self):
        """Response without 'pivots' key should use default."""
        output = AIPlannerOutput.model_validate({"summary": "test"})
        assert output.pivots == []

    def test_pivots_not_a_list(self):
        """Pivots field that isn't a list should fail validation."""
        with pytest.raises(ValidationError):
            AIPlannerOutput.model_validate({"pivots": "not a list"})

    def test_pivot_with_missing_required_fields(self):
        """Pivot missing 'target' and 'action' should fail."""
        with pytest.raises(ValidationError):
            PivotRecommendation.model_validate({"reasoning": "test"})

    def test_pivot_with_invalid_action(self):
        """Pivot with non-existent action should fail."""
        with pytest.raises(ValidationError):
            PivotRecommendation.model_validate({
                "target": "example.com",
                "action": "collect_nonexistent",
            })

    def test_pivot_target_empty_string(self):
        """Pivot with empty target should fail (min_length=1)."""
        with pytest.raises(ValidationError):
            PivotRecommendation.model_validate({
                "target": "",
                "action": "collect_dns",
            })

    def test_pivot_priority_out_of_range(self):
        """Pivot with priority outside 1-10 should fail."""
        with pytest.raises(ValidationError):
            PivotRecommendation.model_validate({
                "target": "example.com",
                "action": "collect_dns",
                "priority": 11,
            })
        with pytest.raises(ValidationError):
            PivotRecommendation.model_validate({
                "target": "example.com",
                "action": "collect_dns",
                "priority": 0,
            })

    def test_truncated_json(self):
        """Truncated JSON should fail parsing."""
        with pytest.raises(ValidationError):
            AIPlannerOutput.model_validate_json('{"pivots": [{"target": "exam')

    def test_invalid_json_syntax(self):
        """Invalid JSON syntax should fail."""
        with pytest.raises(ValidationError):
            AIPlannerOutput.model_validate_json("{not json}")

    def test_array_instead_of_object(self):
        """JSON array instead of object should fail."""
        with pytest.raises(ValidationError):
            AIPlannerOutput.model_validate_json('[{"target": "example.com"}]')

    def test_deeply_nested_garbage(self):
        """Deeply nested invalid structure should fail."""
        with pytest.raises(ValidationError):
            AIPlannerOutput.model_validate({
                "pivots": [
                    {"target": {"nested": "object"}, "action": "collect_dns"}
                ]
            })


class TestMalformedAnalyzerOutput:
    """Tests for handling malformed LLM analyzer responses."""

    def test_empty_analyzer(self):
        """Empty JSON should produce default analyzer output."""
        output = AIAnalyzerOutput.model_validate({})
        assert output.summary == ""
        assert output.risk_level == RiskLevel.LOW
        assert output.key_findings == []

    def test_invalid_risk_level(self):
        """Invalid risk level should fail."""
        with pytest.raises(ValidationError):
            AIAnalyzerOutput.model_validate({"risk_level": "critical_high"})

    def test_findings_not_a_list(self):
        """key_findings that isn't a list should fail."""
        with pytest.raises(ValidationError):
            AIAnalyzerOutput.model_validate({"key_findings": "string"})

    def test_finding_missing_title(self):
        """Finding without title should fail."""
        with pytest.raises(ValidationError):
            AIAnalyzerOutput.model_validate({
                "key_findings": [{"description": "missing title"}]
            })

    def test_finding_confidence_out_of_range(self):
        """Finding with confidence outside 0-1 should fail."""
        with pytest.raises(ValidationError):
            AIAnalyzerOutput.model_validate({
                "key_findings": [{
                    "title": "test",
                    "description": "test",
                    "confidence": 1.5,
                }]
            })


# ── Unsafe pivot tests ──────────────────────────────────────────────────────


class TestUnsafePivots:
    """Tests for detecting and handling unsafe/malicious pivot targets."""

    def test_private_ip_pivot(self):
        """Pivot targeting private IP should still be filterable."""
        pivot = PivotRecommendation(
            target="192.168.1.1",
            action=PivotAction.COLLECT_DNS,
            priority=1,
        )
        # The pivot selector doesn't filter private IPs (the collector does),
        # but the system should handle it gracefully.
        assert pivot.target == "192.168.1.1"

    def test_localhost_pivot(self):
        """Pivot targeting localhost should be handled."""
        pivot = PivotRecommendation(
            target="localhost",
            action=PivotAction.COLLECT_HTTP,
            priority=1,
        )
        assert pivot.target == "localhost"

    def test_extremely_long_target(self):
        """Pivot with extremely long target should fail validation."""
        with pytest.raises(ValidationError):
            PivotRecommendation(
                target="a" * 501,  # max_length=500
                action=PivotAction.COLLECT_DNS,
            )

    def test_script_in_target(self):
        """Pivot with script injection in target should be treated as string."""
        pivot = PivotRecommendation(
            target="<script>alert('xss')</script>",
            action=PivotAction.COLLECT_SEARCH,
            priority=1,
        )
        # Should be stored as-is (sanitization happens at the collector level)
        assert "<script>" in pivot.target

    def test_sql_injection_in_target(self):
        """Pivot with SQL injection should be treated as string."""
        pivot = PivotRecommendation(
            target="'; DROP TABLE investigations;--",
            action=PivotAction.COLLECT_DNS,
            priority=1,
        )
        assert "DROP TABLE" in pivot.target

    def test_all_pivot_actions_are_valid(self):
        """All PivotAction enum values should map to collectors."""
        from app.services.pivot_selector import ACTION_TO_COLLECTOR

        for action in PivotAction:
            assert action in ACTION_TO_COLLECTOR, f"{action} not in ACTION_TO_COLLECTOR"


# ── Budget/depth edge cases ─────────────────────────────────────────────────


class TestBudgetDepthEdgeCases:
    """Tests for budget and depth filtering edge cases."""

    def test_zero_budget_rejects_all(self):
        """Budget of 0 should reject all pivots."""
        pivots = [
            PivotRecommendation(target="a.com", action=PivotAction.COLLECT_DNS),
            PivotRecommendation(target="b.com", action=PivotAction.COLLECT_WHOIS),
        ]
        result = filter_by_budget(pivots, budget_remaining=0)
        assert result == []

    def test_negative_budget_rejects_all(self):
        """Negative budget should reject all pivots."""
        pivots = [PivotRecommendation(target="a.com", action=PivotAction.COLLECT_DNS)]
        result = filter_by_budget(pivots, budget_remaining=-5)
        assert result == []

    def test_budget_one_accepts_one(self):
        """Budget of 1 should accept only 1 pivot."""
        pivots = [
            PivotRecommendation(target="a.com", action=PivotAction.COLLECT_DNS),
            PivotRecommendation(target="b.com", action=PivotAction.COLLECT_WHOIS),
        ]
        result = filter_by_budget(pivots, budget_remaining=1)
        assert len(result) == 1

    def test_empty_pivot_list(self):
        """Empty pivot list should return empty."""
        result = filter_by_budget([], budget_remaining=100)
        assert result == []

    def test_duplicates_with_empty_dispatched(self):
        """No previously dispatched targets means all pivots pass."""
        pivots = [
            PivotRecommendation(target="a.com", action=PivotAction.COLLECT_DNS),
        ]
        result = filter_by_duplicates(pivots, dispatched_targets=set())
        assert len(result) == 1

    def test_all_duplicates_filtered(self):
        """All pivots targeting already-dispatched targets should be filtered."""
        pivots = [
            PivotRecommendation(target="a.com", action=PivotAction.COLLECT_DNS),
            PivotRecommendation(target="b.com", action=PivotAction.COLLECT_DNS),
        ]
        result = filter_by_duplicates(
            pivots, dispatched_targets={"a.com", "b.com"}
        )
        assert result == []

    def test_rate_limit_allows_under_threshold(self):
        """Pivots under rate limit threshold should pass."""
        pivots = [
            PivotRecommendation(target="a.com", action=PivotAction.COLLECT_DNS),
        ]
        result = filter_by_rate_limits(pivots, recent_action_counts={"collect_dns": 5})
        assert len(result) == 1

    def test_rate_limit_blocks_at_threshold(self):
        """Pivots at rate limit threshold (20) should be blocked."""
        pivots = [
            PivotRecommendation(target="a.com", action=PivotAction.COLLECT_DNS),
        ]
        result = filter_by_rate_limits(pivots, recent_action_counts={"collect_dns": 20})
        assert result == []


# ── Deterministic fallback tests ────────────────────────────────────────────


class TestDeterministicFallback:
    """Tests for deterministic behavior when no LLM is configured."""

    def test_all_actions_have_collectors(self):
        """Every PivotAction should have a corresponding collector."""
        from app.services.pivot_selector import ACTION_TO_COLLECTOR

        for action in PivotAction:
            collector_name = ACTION_TO_COLLECTOR.get(action)
            assert collector_name is not None, f"No collector for {action}"

    def test_planner_output_defaults_are_safe(self):
        """Default planner output should be safe (no pivots, no stop)."""
        output = AIPlannerOutput()
        assert output.pivots == []
        assert output.stop_recommended is False
        assert output.summary == ""

    def test_analyzer_output_defaults_are_safe(self):
        """Default analyzer output should be safe."""
        output = AIAnalyzerOutput()
        assert output.risk_level == RiskLevel.LOW
        assert output.key_findings == []
        assert output.recommendations == []

    def test_select_pivots_with_empty_planner(self):
        """Empty planner output should produce no pivots."""
        planner_output = AIPlannerOutput()
        result = select_pivots(
            planner_output,
            budget_remaining=100,
            dispatched_targets=set(),
            recent_action_counts={},
        )
        assert result == []

    def test_all_risk_levels_valid(self):
        """All RiskLevel enum values should be valid."""
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"

    def test_pivot_action_enum_complete(self):
        """PivotAction enum should have all expected values."""
        expected = {
            "collect_dns", "collect_whois", "collect_ct", "collect_ip_asn",
            "collect_github", "collect_http", "collect_threat_intel",
            "collect_reddit", "collect_keybase", "collect_hackernews",
            "collect_gitlab", "collect_search",
        }
        actual = {action.value for action in PivotAction}
        assert expected == actual
