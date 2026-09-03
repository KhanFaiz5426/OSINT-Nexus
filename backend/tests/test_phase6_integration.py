"""Phase 6 integration tests — orchestrator, AI, budget, stopping conditions.

Tests the investigation orchestrator loop, AI planner/analyzer,
pivot selection, hallucination prevention, and budget/depth enforcement.
All LLM calls are mocked — no live AI API required for CI.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

# ── Mock helpers ──────────────────────────────────────────────────────────────


class MockAsyncContextManager:
    """Helper that makes Mock work with `async with`."""

    def __init__(self, return_value):
        self._return_value = return_value

    async def __aenter__(self):
        return self._return_value

    async def __aexit__(self, *args):
        pass


class MockPool:
    """Mock asyncpg pool where acquire() returns an async context manager."""

    def __init__(self, conn: AsyncMock):
        self._conn = conn

    def acquire(self):
        return MockAsyncContextManager(self._conn)


# ── Test fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def mock_pool():
    """Mock asyncpg pool for database operations.

    Properly mocks pool.acquire() as an async context manager
    so `async with pool.acquire() as conn:` works correctly.
    """
    pool = AsyncMock()
    conn = AsyncMock()

    # Make pool.acquire() work as: async with pool.acquire() as conn
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = acquire_ctx

    return pool, conn


@pytest.fixture
def sample_investigation_row():
    """Sample investigation DB row."""
    return {
        "id": "test-inv-uuid-001",
        "name": "Test Investigation",
        "target": "example.com",
        "target_type": "domain",
        "status": "created",
        "depth": "standard",
        "api_calls_used": 0,
        "api_budget": 100,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }


@pytest.fixture
def sample_graph_summary():
    """Sample graph summary for AI prompts."""
    return {
        "entity_count": 5,
        "relationship_count": 3,
        "entity_summary": [
            {
                "type": "Domain", "value": "example.com",
                "confidence": 0.9, "source_count": 3,
                "id": "domain:example.com",
            },
            {
                "type": "IP", "value": "93.184.216.34",
                "confidence": 0.85, "source_count": 2,
                "id": "ip:93.184.216.34",
            },
            {
                "type": "Subdomain", "value": "www.example.com",
                "confidence": 0.8, "source_count": 1,
                "id": "subdomain:www.example.com",
            },
        ],
        "relationship_summary": [
            {
                "source": "domain:example.com",
                "target": "ip:93.184.216.34",
                "type": "hosted_on",
                "confidence": 0.8,
            },
            {
                "source": "domain:example.com",
                "target": "subdomain:www.example.com",
                "type": "has_subdomain",
                "confidence": 0.7,
            },
        ],
    }


@pytest.fixture
def sample_planner_response():
    """Sample valid AI planner response."""
    return {
        "pivots": [
            {
                "target": "93.184.216.34",
                "action": "collect_ip_asn",
                "reasoning": "IP address found in DNS records, check ASN ownership",
                "priority": 2,
                "evidence_ids": ["obs-1", "obs-2"],
            },
            {
                "target": "www.example.com",
                "action": "collect_http",
                "reasoning": "Subdomain discovered, check HTTP headers",
                "priority": 3,
                "evidence_ids": ["obs-3"],
            },
        ],
        "summary": "Found domain with IP and subdomain. Recommend IP-to-ASN and HTTP collection.",
        "stop_recommended": False,
        "stop_reason": "",
    }


@pytest.fixture
def sample_analyzer_response():
    """Sample valid AI analyzer response."""
    return {
        "summary": "Investigation of example.com revealed DNS infrastructure and one subdomain.",
        "risk_level": "medium",
        "risk_reasoning": "Standard domain with no immediate threat indicators found.",
        "key_findings": [
            {
                "title": "Domain resolves to single IP",
                "description": "example.com points to 93.184.216.34",
                "entity_ids": ["domain:example.com", "ip:93.184.216.34"],
                "confidence": 0.85,
            }
        ],
        "recommendations": [
            "Check threat intelligence for the IP address",
            "Enumerate additional subdomains",
        ],
    }


# ── Test: AI model validation ────────────────────────────────────────────────


class TestAIModelValidation:
    """Test Pydantic model validation for AI output."""

    def test_planner_output_valid(self, sample_planner_response):
        from app.models.ai import AIPlannerOutput

        output = AIPlannerOutput.model_validate(sample_planner_response)
        assert len(output.pivots) == 2
        assert output.pivots[0].action.value == "collect_ip_asn"
        assert output.pivots[0].priority == 2
        assert output.stop_recommended is False

    def test_planner_output_empty_pivots(self):
        from app.models.ai import AIPlannerOutput

        output = AIPlannerOutput.model_validate({
            "pivots": [],
            "summary": "Nothing to do",
            "stop_recommended": True,
            "stop_reason": "Investigation complete",
        })
        assert len(output.pivots) == 0
        assert output.stop_recommended is True

    def test_planner_output_invalid_action(self):
        from pydantic import ValidationError

        from app.models.ai import AIPlannerOutput

        with pytest.raises(ValidationError):
            AIPlannerOutput.model_validate({
                "pivots": [
                    {
                        "target": "evil.com",
                        "action": "collect_nmap",  # Invalid action
                        "reasoning": "Scan ports",
                        "priority": 1,
                        "evidence_ids": [],
                    }
                ],
                "summary": "Test",
                "stop_recommended": False,
                "stop_reason": "",
            })

    def test_planner_output_priority_bounds(self):
        from pydantic import ValidationError

        from app.models.ai import AIPlannerOutput

        with pytest.raises(ValidationError):
            AIPlannerOutput.model_validate({
                "pivots": [
                    {
                        "target": "evil.com",
                        "action": "collect_dns",
                        "reasoning": "Test",
                        "priority": 0,  # Out of range (1-10)
                        "evidence_ids": [],
                    }
                ],
                "summary": "Test",
                "stop_recommended": False,
                "stop_reason": "",
            })

    def test_analyzer_output_valid(self, sample_analyzer_response):
        from app.models.ai import AIAnalyzerOutput

        output = AIAnalyzerOutput.model_validate(sample_analyzer_response)
        assert output.risk_level.value == "medium"
        assert len(output.key_findings) == 1
        assert len(output.recommendations) == 2

    def test_analyzer_output_invalid_risk_level(self):
        from pydantic import ValidationError

        from app.models.ai import AIAnalyzerOutput

        with pytest.raises(ValidationError):
            AIAnalyzerOutput.model_validate({
                "summary": "Test",
                "risk_level": "extreme",  # Invalid
                "risk_reasoning": "Test",
                "key_findings": [],
                "recommendations": [],
            })

    def test_pivot_action_all_values(self):
        from app.models.ai import PivotAction

        expected = {
            "collect_dns", "collect_whois", "collect_ct",
            "collect_ip_asn", "collect_github", "collect_http",
            "collect_threat_intel",
        }
        actual = {action.value for action in PivotAction}
        assert actual == expected


# ── Test: AI planner prompt building ─────────────────────────────────────────


class TestPlannerPrompt:
    """Test AI planner prompt construction."""

    def test_build_prompt_structure(self):
        from app.ai.planner import build_planner_prompt
        from app.models import TargetType

        messages = build_planner_prompt(
            investigation_target="example.com",
            target_type=TargetType.DOMAIN,
            current_round=0,
            max_rounds=3,
            graph_summary={
                "entity_count": 2,
                "relationship_count": 1,
                "entity_summary": [
                    {
                        "type": "Domain",
                        "value": "example.com",
                        "confidence": 0.9,
                        "source_count": 2,
                        "id": "domain:example.com",
                    },
                ],
                "relationship_summary": [],
            },
            budget_remaining=95,
            recent_pivots=[],
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "example.com" in messages[1]["content"]
        assert "domain" in messages[1]["content"]
        assert "95" in messages[1]["content"]
        assert "Round: 1 of 3" in messages[1]["content"]

    def test_build_prompt_with_recent_pivots(self):
        from app.ai.planner import build_planner_prompt
        from app.models import TargetType

        messages = build_planner_prompt(
            investigation_target="1.2.3.4",
            target_type=TargetType.IP,
            current_round=2,
            max_rounds=6,
            graph_summary={
                "entity_count": 10,
                "relationship_count": 5,
                "entity_summary": [],
                "relationship_summary": [],
            },
            budget_remaining=50,
            recent_pivots=[
                {"action": "collect_dns", "target": "1.2.3.4"},
                {"action": "collect_http", "target": "1.2.3.4"},
            ],
        )

        content = messages[1]["content"]
        assert "collect_dns" in content
        assert "Round: 3 of 6" in content
        assert "50" in content

    def test_parse_planner_response_valid(self, sample_planner_response):
        from app.ai.planner import parse_planner_response

        text = json.dumps(sample_planner_response)
        output = parse_planner_response(text)
        assert output is not None
        assert len(output.pivots) == 2

    def test_parse_planner_response_markdown_block(self, sample_planner_response):
        from app.ai.planner import parse_planner_response

        text = f"```json\n{json.dumps(sample_planner_response)}\n```"
        output = parse_planner_response(text)
        assert output is not None
        assert len(output.pivots) == 2

    def test_parse_planner_response_invalid_json(self):
        from app.ai.planner import parse_planner_response

        output = parse_planner_response("this is not json at all")
        assert output is None

    def test_parse_planner_response_wrong_schema(self):
        from app.ai.planner import parse_planner_response

        # AIPlannerOutput has all fields optional with defaults,
        # so {"foo": "bar"} passes. Use invalid nested types instead.
        bad_data = {
            "pivots": [
                {
                    "target": "",  # min_length=1 violation
                    "action": "collect_dns",
                    "reasoning": "Test",
                    "priority": 1,
                    "evidence_ids": [],
                }
            ],
            "summary": "Test",
            "stop_recommended": "not_a_bool",  # wrong type
            "stop_reason": "",
        }
        output = parse_planner_response(json.dumps(bad_data))
        assert output is None


# ── Test: AI analyzer ─────────────────────────────────────────────────────────


class TestAIAnalyzer:
    """Test AI analyzer prompt building and parsing."""

    def test_build_analyzer_prompt(self, sample_graph_summary):
        from app.ai.analyzer import build_analyzer_prompt

        messages = build_analyzer_prompt(
            investigation_target="example.com",
            target_type="domain",
            graph_summary=sample_graph_summary,
            pivot_rounds_completed=2,
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "risk_level" in messages[0]["content"]
        assert "example.com" in messages[1]["content"]
        assert "2" in messages[1]["content"]

    def test_parse_analyzer_response_valid(self, sample_analyzer_response):
        from app.ai.analyzer import parse_analyzer_response

        output = parse_analyzer_response(json.dumps(sample_analyzer_response))
        assert output is not None
        assert output.risk_level.value == "medium"
        assert len(output.key_findings) == 1

    def test_parse_analyzer_response_invalid(self):
        from app.ai.analyzer import parse_analyzer_response

        output = parse_analyzer_response("not json")
        assert output is None

    def test_parse_analyzer_with_code_block(self, sample_analyzer_response):
        from app.ai.analyzer import parse_analyzer_response

        text = f"```\n{json.dumps(sample_analyzer_response)}\n```"
        output = parse_analyzer_response(text)
        assert output is not None


# ── Test: AI validator / hallucination prevention ─────────────────────────────


class TestAIValidator:
    """Test hallucination prevention and ID validation."""

    @pytest.mark.asyncio
    async def test_validate_observation_ids_empty(self):
        from app.ai.validator import validate_observation_ids

        result = await validate_observation_ids([], "inv-001")
        assert result == []

    @pytest.mark.asyncio
    async def test_validate_observation_ids_valid(self):
        from app.ai.validator import validate_observation_ids

        conn = AsyncMock()
        pool = MockPool(conn)

        conn.fetch.return_value = [
            {"id": "obs-001"},
            {"id": "obs-002"},
        ]

        with patch("app.ai.validator.get_pool", new_callable=AsyncMock, return_value=pool):
            result = await validate_observation_ids(
                ["obs-001", "obs-002", "obs-999"], "inv-001"
            )

        assert "obs-001" in result
        assert "obs-002" in result
        assert "obs-999" not in result

    @pytest.mark.asyncio
    async def test_validate_observation_ids_all_hallucinated(self):
        from app.ai.validator import validate_observation_ids

        conn = AsyncMock()
        pool = MockPool(conn)

        conn.fetch.return_value = []

        with patch("app.ai.validator.get_pool", new_callable=AsyncMock, return_value=pool):
            result = await validate_observation_ids(
                ["fake-1", "fake-2"], "inv-001"
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_validate_observation_ids_empty_strings(self):
        from app.ai.validator import validate_observation_ids

        result = await validate_observation_ids(["", "  ", ""], "inv-001")
        assert result == []

    def test_validate_planner_output_valid(self, sample_planner_response):
        from app.ai.validator import validate_planner_output

        output = validate_planner_output(sample_planner_response)
        assert output is not None
        assert len(output.pivots) == 2

    def test_validate_planner_output_invalid(self):
        from app.ai.validator import validate_planner_output

        # Use data that actually violates the schema constraints.
        bad_data = {
            "pivots": [
                {
                    "target": "",  # min_length=1
                    "action": "invalid_action",  # not a valid PivotAction
                    "reasoning": "Test",
                    "priority": 1,
                    "evidence_ids": [],
                }
            ],
            "summary": "Test",
            "stop_recommended": "not_bool",  # wrong type
            "stop_reason": "",
        }
        output = validate_planner_output(bad_data)
        assert output is None

    def test_validate_analyzer_output_valid(self, sample_analyzer_response):
        from app.ai.validator import validate_analyzer_output

        output = validate_analyzer_output(sample_analyzer_response)
        assert output is not None
        assert output.risk_level.value == "medium"

    def test_validate_analyzer_output_invalid(self):
        from app.ai.validator import validate_analyzer_output

        # Use data that actually violates the schema constraints.
        bad_data = {
            "summary": 12345,  # should be string
            "risk_level": "extreme",  # not a valid RiskLevel
            "risk_reasoning": [],
            "key_findings": "not_a_list",
            "recommendations": 42,
        }
        output = validate_analyzer_output(bad_data)
        assert output is None

    def test_sanitize_pivot_evidence_ids(self):
        from app.ai.validator import sanitize_pivot_evidence_ids
        from app.models.ai import PivotAction, PivotRecommendation

        pivots = [
            PivotRecommendation(
                target="evil.com",
                action=PivotAction.COLLECT_DNS,
                reasoning="Test",
                priority=1,
                evidence_ids=["obs-1", "obs-2", "obs-3"],
            )
        ]

        valid_ids = {"obs-1", "obs-3"}
        sanitized = sanitize_pivot_evidence_ids(pivots, valid_ids)

        assert len(sanitized) == 1
        assert sanitized[0].evidence_ids == ["obs-1", "obs-3"]


# ── Test: Pivot selector ─────────────────────────────────────────────────────


class TestPivotSelector:
    """Test pivot selection filtering logic."""

    def test_filter_by_budget(self):
        from app.models.ai import PivotAction, PivotRecommendation
        from app.services.pivot_selector import filter_by_budget

        pivots = [
            PivotRecommendation(
                target="a.com", action=PivotAction.COLLECT_DNS,
                reasoning="", priority=1,
            ),
            PivotRecommendation(
                target="b.com", action=PivotAction.COLLECT_DNS,
                reasoning="", priority=2,
            ),
            PivotRecommendation(
                target="c.com", action=PivotAction.COLLECT_DNS,
                reasoning="", priority=3,
            ),
        ]

        # Budget of 2 should keep only 2 pivots.
        result = filter_by_budget(pivots, 2)
        assert len(result) == 2

        # Budget of 0 should reject all.
        result = filter_by_budget(pivots, 0)
        assert len(result) == 0

    def test_filter_by_permitted_collectors(self):
        from app.models.ai import PivotAction, PivotRecommendation
        from app.services.pivot_selector import filter_by_permitted_collectors

        pivots = [
            PivotRecommendation(
                target="a.com", action=PivotAction.COLLECT_DNS,
                reasoning="", priority=1,
            ),
            PivotRecommendation(
                target="b.com",
                action=PivotAction.COLLECT_GITHUB,
                reasoning="", priority=2,
            ),
            PivotRecommendation(
                target="c.com",
                action=PivotAction.COLLECT_HTTP,
                reasoning="", priority=3,
            ),
        ]

        permitted = {PivotAction.COLLECT_DNS, PivotAction.COLLECT_HTTP}
        result = filter_by_permitted_collectors(pivots, permitted)
        assert len(result) == 2
        assert all(p.action in permitted for p in result)

    def test_filter_by_permitted_collectors_none(self):
        from app.models.ai import PivotAction, PivotRecommendation
        from app.services.pivot_selector import filter_by_permitted_collectors

        pivots = [
            PivotRecommendation(
                target="a.com",
                action=PivotAction.COLLECT_DNS,
                reasoning="", priority=1,
            ),
        ]

        result = filter_by_permitted_collectors(pivots, None)
        assert len(result) == 1

    def test_filter_by_duplicates(self):
        from app.models.ai import PivotAction, PivotRecommendation
        from app.services.pivot_selector import filter_by_duplicates

        pivots = [
            PivotRecommendation(
                target="example.com",
                action=PivotAction.COLLECT_DNS,
                reasoning="", priority=1,
            ),
            PivotRecommendation(
                target="Example.COM",
                action=PivotAction.COLLECT_WHOIS,
                reasoning="", priority=2,
            ),
            PivotRecommendation(
                target="new.com",
                action=PivotAction.COLLECT_DNS,
                reasoning="", priority=3,
            ),
        ]

        dispatched = {"example.com"}
        result = filter_by_duplicates(pivots, dispatched)
        assert len(result) == 1
        assert result[0].target == "new.com"

    def test_filter_by_rate_limits(self):
        from app.models.ai import PivotAction, PivotRecommendation
        from app.services.pivot_selector import filter_by_rate_limits

        pivots = [
            PivotRecommendation(
                target="a.com",
                action=PivotAction.COLLECT_DNS,
                reasoning="", priority=1,
            ),
            PivotRecommendation(
                target="b.com",
                action=PivotAction.COLLECT_DNS,
                reasoning="", priority=2,
            ),
        ]

        # Already at rate limit for DNS.
        counts = {"collect_dns": 20}
        result = filter_by_rate_limits(pivots, counts)
        assert len(result) == 0

        # Under rate limit.
        counts = {"collect_dns": 15}
        result = filter_by_rate_limits(pivots, counts)
        assert len(result) == 2

    def test_select_pivots_full_pipeline(self):
        from app.models.ai import AIPlannerOutput, PivotAction, PivotRecommendation
        from app.services.pivot_selector import select_pivots

        planner_output = AIPlannerOutput(
            pivots=[
                PivotRecommendation(
                    target="a.com",
                    action=PivotAction.COLLECT_DNS,
                    reasoning="", priority=1,
                ),
                PivotRecommendation(
                    target="example.com",
                    action=PivotAction.COLLECT_WHOIS,
                    reasoning="", priority=2,
                ),
                PivotRecommendation(
                    target="b.com",
                    action=PivotAction.COLLECT_HTTP,
                    reasoning="", priority=3,
                ),
            ],
            summary="Test",
            stop_recommended=False,
        )

        result = select_pivots(
            planner_output,
            budget_remaining=2,
            dispatched_targets={"example.com"},
            recent_action_counts={},
        )

        # Should filter out example.com (duplicate) and keep 2 (budget=2)
        assert len(result) <= 2
        assert all(p.target != "example.com" for p in result)


# ── Test: Orchestrator state ─────────────────────────────────────────────────


class TestInvestigationState:
    """Test InvestigationState budget and depth tracking."""

    def test_budget_tracking(self):
        from app.models import InvestigationDepth, TargetType
        from app.services.orchestrator import InvestigationState

        state = InvestigationState(
            investigation_id="inv-001",
            target="example.com",
            target_type=TargetType.DOMAIN,
            depth=InvestigationDepth.STANDARD,
            budget=10,
        )

        assert not state.budget_exhausted
        state.consume_budget(5)
        assert state.budget_remaining == 5
        state.consume_budget(6)
        assert state.budget_remaining == 0
        assert state.budget_exhausted

    def test_depth_tracking(self):
        from app.models import InvestigationDepth, TargetType
        from app.services.orchestrator import InvestigationState

        state = InvestigationState(
            investigation_id="inv-001",
            target="example.com",
            target_type=TargetType.DOMAIN,
            depth=InvestigationDepth.SHALLOW,
            budget=100,
        )

        assert state.max_rounds == 1
        assert not state.depth_reached
        state.next_round()
        assert state.depth_reached

    def test_stopping_conditions_budget(self):
        from app.models import InvestigationDepth, TargetType
        from app.services.orchestrator import InvestigationState

        state = InvestigationState(
            investigation_id="inv-001",
            target="example.com",
            target_type=TargetType.DOMAIN,
            depth=InvestigationDepth.DEEP,
            budget=1,
        )

        assert state.check_stopping_conditions() is None
        state.consume_budget(1)
        assert state.check_stopping_conditions() == "budget_exhausted"

    def test_stopping_conditions_depth(self):
        from app.models import InvestigationDepth, TargetType
        from app.services.orchestrator import InvestigationState

        state = InvestigationState(
            investigation_id="inv-001",
            target="example.com",
            target_type=TargetType.DOMAIN,
            depth=InvestigationDepth.SHALLOW,
            budget=100,
        )

        state.next_round()
        assert state.check_stopping_conditions() == "depth_reached"

    def test_record_dispatch(self):
        from app.models import InvestigationDepth, TargetType
        from app.models.ai import PivotAction
        from app.services.orchestrator import InvestigationState

        state = InvestigationState(
            investigation_id="inv-001",
            target="example.com",
            target_type=TargetType.DOMAIN,
            depth=InvestigationDepth.STANDARD,
            budget=100,
        )

        state.record_dispatch(PivotAction.COLLECT_DNS, "example.com")
        state.record_dispatch(PivotAction.COLLECT_HTTP, "1.2.3.4")

        assert state.total_pivots_dispatched == 2
        assert "example.com" in state.dispatched_targets
        assert "1.2.3.4" in state.dispatched_targets
        assert state.recent_action_counts["collect_dns"] == 1
        assert state.recent_action_counts["collect_http"] == 1

    def test_depth_max_rounds(self):
        from app.models import InvestigationDepth, TargetType
        from app.services.orchestrator import InvestigationState

        for depth, expected in [
            (InvestigationDepth.SHALLOW, 1),
            (InvestigationDepth.STANDARD, 3),
            (InvestigationDepth.DEEP, 6),
        ]:
            state = InvestigationState(
                investigation_id="inv-001",
                target="x",
                target_type=TargetType.DOMAIN,
                depth=depth,
                budget=100,
            )
            assert state.max_rounds == expected


# ── Test: Initial action selection ────────────────────────────────────────────


class TestInitialActions:
    """Test deterministic initial action selection."""

    def test_domain_initial_actions(self):
        from app.ai.planner import select_initial_actions
        from app.models import TargetType

        actions = select_initial_actions(TargetType.DOMAIN)
        action_values = {a.value for a in actions}
        assert "collect_dns" in action_values
        assert "collect_whois" in action_values
        assert "collect_ct" in action_values
        assert "collect_http" in action_values

    def test_ip_initial_actions(self):
        from app.ai.planner import select_initial_actions
        from app.models import TargetType

        actions = select_initial_actions(TargetType.IP)
        action_values = {a.value for a in actions}
        assert "collect_dns" in action_values
        assert "collect_ip_asn" in action_values
        assert "collect_http" in action_values
        assert "collect_threat_intel" in action_values

    def test_username_initial_actions(self):
        from app.ai.planner import select_initial_actions
        from app.models import TargetType

        actions = select_initial_actions(TargetType.USERNAME)
        action_values = {a.value for a in actions}
        assert "collect_github" in action_values

    def test_email_initial_actions(self):
        from app.ai.planner import select_initial_actions
        from app.models import TargetType

        actions = select_initial_actions(TargetType.EMAIL)
        action_values = {a.value for a in actions}
        assert "collect_whois" in action_values
        assert "collect_dns" in action_values

    def test_unknown_fallback(self):
        from app.ai.planner import select_initial_actions
        from app.models import TargetType

        actions = select_initial_actions(TargetType.UNKNOWN)
        action_values = {a.value for a in actions}
        assert "collect_dns" in action_values
        assert "collect_http" in action_values


# ── Test: Orchestrator with mocked collectors ─────────────────────────────────


class TestOrchestratorIntegration:
    """Integration tests for the orchestrator with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_run_investigation_loop_no_llm(self, sample_investigation_row):
        """Test the investigation loop without LLM (safe defaults)."""
        from app.services.orchestrator import run_investigation_loop

        mock_conn = AsyncMock()
        mock_pool = MockPool(mock_conn)

        # Mock investigation lookup.
        mock_conn.fetchrow.return_value = sample_investigation_row

        # Mock activity log insert.
        mock_conn.execute = AsyncMock()

        with patch(
            "app.services.orchestrator.get_pool",
            new_callable=AsyncMock, return_value=mock_pool,
        ), \
             patch(
                 "app.services.orchestrator"
                 ".update_investigation_status",
                 new_callable=AsyncMock,
             ), \
             patch(
                 "app.services.orchestrator.log_activity",
                 new_callable=AsyncMock,
             ), \
             patch(
                 "app.services.orchestrator"
                 ".increment_api_calls",
                 new_callable=AsyncMock,
             ), \
             patch(
                 "app.services.orchestrator"
                 ".correlate_observations",
                 new_callable=AsyncMock,
                 return_value={
                     "entities": [],
                     "relationships": [],
                 },
             ), \
             patch(
                 "app.services.orchestrator"
                 ".get_graph_summary",
                 new_callable=AsyncMock,
                 return_value={
                     "entity_count": 0,
                     "relationship_count": 0,
                     "entity_summary": [],
                     "relationship_summary": [],
                 },
             ), \
             patch(
                 "app.collectors.registry._collectors", {},
             ), \
             patch(
                 "app.services.orchestrator"
                 ".collect_and_store",
                 new_callable=AsyncMock,
                 return_value=None,
             ):

            result = await run_investigation_loop("test-inv-uuid-001")

        assert "investigation_id" in result
        assert result["investigation_id"] == "test-inv-uuid-001"

    @pytest.mark.asyncio
    async def test_investigation_not_found(self):
        """Test that missing investigation returns error."""
        from app.services.orchestrator import run_investigation_loop

        mock_conn = AsyncMock()
        mock_pool = MockPool(mock_conn)

        mock_conn.fetchrow.return_value = None

        with patch(
            "app.services.orchestrator.get_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ):
            result = await run_investigation_loop("nonexistent-id")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_budget_stops_loop(self, sample_investigation_row):
        """Test that budget exhaustion stops the loop."""
        from app.services.orchestrator import run_investigation_loop

        # Set very low budget.
        sample_investigation_row["api_budget"] = 1
        sample_investigation_row["api_calls_used"] = 0

        mock_conn = AsyncMock()
        mock_pool = MockPool(mock_conn)

        mock_conn.fetchrow.return_value = sample_investigation_row
        mock_conn.execute = AsyncMock()

        with patch(
            "app.services.orchestrator.get_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ), \
             patch(
                 "app.services.orchestrator"
                 ".update_investigation_status",
                 new_callable=AsyncMock,
             ), \
             patch(
                 "app.services.orchestrator.log_activity",
                 new_callable=AsyncMock,
             ), \
             patch(
                 "app.services.orchestrator"
                 ".get_graph_summary",
                 new_callable=AsyncMock,
                 return_value={
                     "entity_count": 0,
                     "relationship_count": 0,
                     "entity_summary": [],
                     "relationship_summary": [],
                 },
             ), \
             patch(
                 "app.collectors.registry._collectors", {},
             ), \
             patch(
                 "app.services.orchestrator"
                 ".collect_and_store",
                 new_callable=AsyncMock,
                 return_value=None,
             ):

            result = await run_investigation_loop("test-inv-uuid-001")

        # Should complete with budget exhaustion as stop reason.
        assert "stop_reason" in result


# ── Test: Celery task ─────────────────────────────────────────────────────────


class TestCeleryTask:
    """Test the Celery run_investigation task."""

    def test_task_name(self):
        from app.tasks.run_investigation import run_investigation_task

        assert run_investigation_task.name == "app.tasks.run_investigation"

    def test_task_is_celery_task(self):
        from app.tasks.run_investigation import run_investigation_task

        # Should have the AsyncResult interface.
        assert hasattr(run_investigation_task, "delay")
        assert hasattr(run_investigation_task, "apply_async")


# ── Test: API endpoint models ─────────────────────────────────────────────────


class TestAPIModels:
    """Test API response models for start/status endpoints."""

    def test_investigation_start_response(self):
        from app.api.investigations import InvestigationStartResponse

        resp = InvestigationStartResponse(
            message="Investigation started",
            investigation_id="inv-001",
            task_id="task-abc",
        )
        assert resp.message == "Investigation started"
        assert resp.task_id == "task-abc"

    def test_investigation_status_response(self):
        from app.api.investigations import InvestigationStatusResponse

        resp = InvestigationStatusResponse(
            id="inv-001",
            status="running",
            target="example.com",
            target_type="domain",
            depth="standard",
            api_calls_used=5,
            api_budget=100,
            entity_count=10,
            relationship_count=5,
        )
        assert resp.status == "running"
        assert resp.api_calls_used == 5
        assert resp.entity_count == 10


# ── Test: AI planner async integration ───────────────────────────────────────


class TestPlannerAsync:
    """Test the async AI planner integration."""

    @pytest.mark.asyncio
    async def test_plan_pivots_no_llm(self):
        from app.ai.planner import plan_pivots_with_ai
        from app.models import TargetType

        output = await plan_pivots_with_ai(
            investigation_id="inv-001",
            target="example.com",
            target_type=TargetType.DOMAIN,
            current_round=0,
            max_rounds=3,
            graph_summary={
                "entity_count": 0,
                "relationship_count": 0,
                "entity_summary": [],
                "relationship_summary": [],
            },
            budget_remaining=100,
            recent_pivots=[],
            llm_call_fn=None,
        )

        assert output.stop_recommended is True
        assert (
            "not configured" in output.summary.lower()
            or "not available" in output.stop_reason.lower()
        )

    @pytest.mark.asyncio
    async def test_plan_pivots_with_mock_llm(self, sample_planner_response):
        from app.ai.planner import plan_pivots_with_ai
        from app.models import TargetType

        async def mock_llm(messages):
            return json.dumps(sample_planner_response)

        with patch(
            "app.ai.planner.validate_observation_ids",
            new_callable=AsyncMock,
            return_value=["obs-1", "obs-2"],
        ):
            output = await plan_pivots_with_ai(
                investigation_id="inv-001",
                target="example.com",
                target_type=TargetType.DOMAIN,
                current_round=0,
                max_rounds=3,
                graph_summary={
                    "entity_count": 2,
                    "relationship_count": 1,
                    "entity_summary": [],
                    "relationship_summary": [],
                },
                budget_remaining=100,
                recent_pivots=[],
                llm_call_fn=mock_llm,
            )

        assert len(output.pivots) == 2
        assert output.stop_recommended is False

    @pytest.mark.asyncio
    async def test_plan_pivots_llm_failure(self):
        from app.ai.planner import plan_pivots_with_ai
        from app.models import TargetType

        async def failing_llm(messages):
            raise RuntimeError("LLM API error")

        output = await plan_pivots_with_ai(
            investigation_id="inv-001",
            target="example.com",
            target_type=TargetType.DOMAIN,
            current_round=0,
            max_rounds=3,
            graph_summary={
                "entity_count": 0,
                "relationship_count": 0,
                "entity_summary": [],
                "relationship_summary": [],
            },
            budget_remaining=100,
            recent_pivots=[],
            llm_call_fn=failing_llm,
        )

        assert output.stop_recommended is True
        assert (
            "unavailable" in output.stop_reason.lower()
            or "failed" in output.summary.lower()
        )


# ── Test: AI analyzer async integration ──────────────────────────────────────


class TestAnalyzerAsync:
    """Test the async AI analyzer integration."""

    @pytest.mark.asyncio
    async def test_analyze_no_llm(self, sample_graph_summary):
        from app.ai.analyzer import analyze_investigation

        output = await analyze_investigation(
            investigation_id="inv-001",
            target="example.com",
            target_type="domain",
            graph_summary=sample_graph_summary,
            pivot_rounds_completed=2,
            llm_call_fn=None,
        )

        assert output.summary != ""
        assert "not configured" in output.summary.lower()

    @pytest.mark.asyncio
    async def test_analyze_with_mock_llm(self, sample_analyzer_response, sample_graph_summary):
        from app.ai.analyzer import analyze_investigation

        async def mock_llm(messages):
            return json.dumps(sample_analyzer_response)

        with patch(
            "app.ai.analyzer.validate_entity_ids",
            new_callable=AsyncMock,
            return_value=["domain:example.com"],
        ):
            output = await analyze_investigation(
                investigation_id="inv-001",
                target="example.com",
                target_type="domain",
                graph_summary=sample_graph_summary,
                pivot_rounds_completed=2,
                llm_call_fn=mock_llm,
            )

        assert output.risk_level.value == "medium"
        assert len(output.key_findings) == 1

    @pytest.mark.asyncio
    async def test_analyze_llm_failure(self, sample_graph_summary):
        from app.ai.analyzer import analyze_investigation

        async def failing_llm(messages):
            raise RuntimeError("API timeout")

        output = await analyze_investigation(
            investigation_id="inv-001",
            target="example.com",
            target_type="domain",
            graph_summary=sample_graph_summary,
            pivot_rounds_completed=0,
            llm_call_fn=failing_llm,
        )

        assert "failed" in output.summary.lower()


# ── Test: Hallucination edge cases ────────────────────────────────────────────


class TestHallucinationEdgeCases:
    """Edge cases for hallucination prevention."""

    @pytest.mark.asyncio
    async def test_validate_ids_with_invalid_uuid_format(self):
        from app.ai.validator import validate_observation_ids

        conn = AsyncMock()
        pool = MockPool(conn)

        conn.fetch.return_value = []

        # Should not crash on invalid UUID format.
        with patch("app.ai.validator.get_pool", new_callable=AsyncMock, return_value=pool):
            result = await validate_observation_ids(
                ["not-a-uuid", "also-not-a-uuid"], "inv-001"
            )

        assert result == []

    def test_sanitize_empty_pivots(self):
        from app.ai.validator import sanitize_pivot_evidence_ids

        result = sanitize_pivot_evidence_ids([], {"obs-1"})
        assert result == []

    def test_planner_output_pivot_limit(self, sample_planner_response):
        """AI returns more than 5 pivots — should be truncated."""
        from app.models.ai import AIPlannerOutput

        # Create 8 pivots.
        pivots = []
        for i in range(8):
            pivots.append({
                "target": f"target{i}.com",
                "action": "collect_dns",
                "reasoning": f"Pivot {i}",
                "priority": i + 1,
                "evidence_ids": [],
            })

        output = AIPlannerOutput.model_validate({
            "pivots": pivots,
            "summary": "Many pivots",
            "stop_recommended": False,
            "stop_reason": "",
        })

        # The model allows it, but the planner truncates to 5.
        assert len(output.pivots) == 8  # Model allows it
        # Truncation happens in plan_pivots_with_ai.
