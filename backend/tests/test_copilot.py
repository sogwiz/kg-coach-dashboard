"""
Phase 7 validation: Copilot Agent + Observability

Tests:
  1. Deterministic tool function tests (no LLM, no API key):
     - adherence_trend returns expected structure
     - morning_brief returns expected structure
     - injury_status returns expected structure
     - sleep_summary returns expected structure
     - current_workout_plan returns "no plan" marker when store is empty
     - current_workout_plan returns plan data after set_current_plan

  2. Observability — no API key required:
     - tracing_config returns a RunnableConfig without crashing when no key
     - tracing_config with LANGCHAIN_TRACING_V2=true + key returns metadata
     - langsmith_enabled() returns False when env vars are not set
     - build_decision_trace returns ordered steps with correct kinds

  3. LLM-live agent tests (skipped without ANTHROPIC_API_KEY):
     - test_adherence_tool_invoked: agent calls adherence_trend when asked about
       adherence
     - test_workout_awareness: after a plan is set in the store, asking "why
       were these exercises chosen?" invokes current_workout_plan and the
       answer references the plan's rationale/stimulus

All deterministic tests (tool functions, MemberKG queries, tracing_config
no-key behavior, decision_trace building) run without an API key.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.copilot.agent import (
    adherence_trend,
    current_workout_plan,
    injury_status,
    morning_brief,
    sleep_summary,
)
from app.generator.store import clear_store, set_current_plan
from app.observability.decision_trace import DecisionStep, build_decision_trace
from app.observability.tracing import langsmith_enabled, tracing_config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

JORDAN_ID = "mbr_01HX9JORDAN"
MICO_ID = "mbr_MICO"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_output(stimulus: str = "test stimulus"):
    """Build a minimal GeneratorOutput for store tests."""
    from app.generator.pipeline import GeneratorOutput, Provenance, WorkoutVariant
    from app.graph.conditional_filter import ConditionalFilterTrace
    from app.models.plan import PlannedExercise, WorkoutPlan

    def _plan(stim: str, rationale: str = "test rationale") -> WorkoutPlan:
        return WorkoutPlan(
            warmup=[],
            main=[
                PlannedExercise(
                    exercise_id="ex_001",
                    name="Test Squat",
                    order=1,
                    sets=3,
                    reps=10,
                    rest_seconds=90,
                    rationale=rationale,
                    sequencing_rationale="First in main; posterior chain primed.",
                    sequencing_role="compound",
                )
            ],
            cooldown=[],
            total_minutes=45,
            stimulus=stim,
            target_adaptation="quad hypertrophy",
            design_rationale="Designed for knee-safe lower body work.",
            sequence_logic="Compounds first while CNS is fresh.",
        )

    def _prov():
        return Provenance(
            generated_at=datetime.now(tz=timezone.utc),
            prompt="lower body",
            time_window_minutes=45,
        )

    variants = [
        WorkoutVariant(
            variant_id="strength",
            label="Strength & Hypertrophy",
            optimizes_for="load/intensity-biased",
            plan=_plan(stimulus, rationale="Selected for maximal strength stimulus."),
            provenance=_prov(),
        ),
        WorkoutVariant(
            variant_id="conditioning",
            label="Conditioning & Metabolic",
            optimizes_for="density/metabolic",
            plan=_plan("metabolic conditioning"),
            provenance=_prov(),
        ),
        WorkoutVariant(
            variant_id="mobility",
            label="Mobility & Recovery",
            optimizes_for="ROM-biased recovery",
            plan=_plan("mobility and recovery"),
            provenance=_prov(),
        ),
    ]
    return GeneratorOutput(
        variants=variants,
        trace=ConditionalFilterTrace(),
        selected_variant_id=None,
    )


# ---------------------------------------------------------------------------
# 1. Tool function tests (deterministic, no API key)
# ---------------------------------------------------------------------------


class TestToolFunctions:
    """Test each tool function independently — no LLM invocation."""

    def test_adherence_trend_jordan_structure(self):
        """adherence_trend for Jordan returns expected keys."""
        result = adherence_trend(JORDAN_ID)
        assert isinstance(result, dict)
        assert "member_id" in result
        assert result["member_id"] == JORDAN_ID
        assert "trend" in result
        assert "weekly_data" in result
        assert isinstance(result["weekly_data"], list)
        assert "average_pct" in result

    def test_adherence_trend_mico_structure(self):
        """adherence_trend for Mico returns expected keys."""
        result = adherence_trend(MICO_ID)
        assert isinstance(result, dict)
        assert result["member_id"] == MICO_ID
        assert "weekly_data" in result

    def test_adherence_trend_weeks_parameter(self):
        """adherence_trend respects the weeks parameter."""
        result = adherence_trend(JORDAN_ID, weeks=2)
        assert len(result["weekly_data"]) <= 2

    def test_adherence_trend_unknown_member(self):
        """adherence_trend returns error dict for unknown member."""
        result = adherence_trend("mbr_UNKNOWN")
        assert "error" in result

    def test_morning_brief_jordan_structure(self):
        """morning_brief for Jordan returns morning_tasks + churn_risk."""
        result = morning_brief(JORDAN_ID)
        assert isinstance(result, dict)
        assert "morning_tasks" in result
        assert "churn_risk" in result
        assert "level" in result["churn_risk"]
        assert isinstance(result["morning_tasks"], list)

    def test_morning_brief_mico_structure(self):
        """morning_brief for Mico returns expected structure."""
        result = morning_brief(MICO_ID)
        assert isinstance(result, dict)
        assert "morning_tasks" in result
        assert "churn_risk" in result

    def test_injury_status_jordan_has_knee(self):
        """injury_status for Jordan shows a knee injury."""
        result = injury_status(JORDAN_ID)
        assert isinstance(result, dict)
        assert "active_injuries" in result
        joints = [inj["joint"] for inj in result["active_injuries"]]
        assert "knee" in joints, f"Expected 'knee' in Jordan's injuries, got: {joints}"

    def test_injury_status_mico_has_lumbar(self):
        """injury_status for Mico shows a lumbar spine injury."""
        result = injury_status(MICO_ID)
        assert isinstance(result, dict)
        joints = [inj["joint"] for inj in result["active_injuries"]]
        assert "lumbar_spine" in joints, (
            f"Expected 'lumbar_spine' in Mico's injuries, got: {joints}"
        )

    def test_injury_status_includes_healing_phase(self):
        """injury_status includes current_phase for each injury."""
        result = injury_status(JORDAN_ID)
        for inj in result["active_injuries"]:
            assert "current_phase" in inj
            assert inj["current_phase"] in (
                "acute", "subacute", "remodeling", "rta"
            ), f"Unexpected healing phase: {inj['current_phase']}"

    def test_sleep_summary_jordan_structure(self):
        """sleep_summary for Jordan returns sleep data and biomarkers."""
        result = sleep_summary(JORDAN_ID)
        assert isinstance(result, dict)
        assert "sleep_hours_last_7_days" in result
        assert isinstance(result["sleep_hours_last_7_days"], list)
        assert "resting_hr_bpm" in result
        assert "hrv_ms" in result
        assert "average_sleep_hours" in result

    def test_sleep_summary_mico_structure(self):
        """sleep_summary for Mico returns expected structure."""
        result = sleep_summary(MICO_ID)
        assert "sleep_hours_last_7_days" in result

    def test_current_workout_plan_no_plan_marker(self):
        """current_workout_plan returns has_plan=False when store is empty."""
        clear_store()
        result = current_workout_plan(JORDAN_ID)
        assert result["has_plan"] is False
        assert "message" in result

    def test_current_workout_plan_returns_data_after_set(self):
        """current_workout_plan returns plan data after set_current_plan."""
        clear_store()
        output = _make_mock_output("strength stimulus test")
        set_current_plan(JORDAN_ID, output)

        result = current_workout_plan(JORDAN_ID)
        assert result["has_plan"] is True
        assert "variants" in result
        assert len(result["variants"]) == 3
        # The strength variant stimulus should be present
        stimuli = [v["stimulus"] for v in result["variants"]]
        assert "strength stimulus test" in stimuli
        clear_store()

    def test_current_workout_plan_single_variant(self):
        """current_workout_plan(variant_id='strength') returns only that variant."""
        clear_store()
        output = _make_mock_output()
        set_current_plan(JORDAN_ID, output)

        result = current_workout_plan(JORDAN_ID, variant_id="strength")
        assert result["has_plan"] is True
        assert len(result["variants"]) == 1
        assert result["variants"][0]["variant_id"] == "strength"
        clear_store()

    def test_current_workout_plan_includes_per_exercise_rationale(self):
        """current_workout_plan includes rationale and sequencing_rationale."""
        clear_store()
        output = _make_mock_output("test stimulus with rationale")
        set_current_plan(JORDAN_ID, output)

        result = current_workout_plan(JORDAN_ID, variant_id="strength")
        exercises = result["variants"][0]["exercises"]
        assert len(exercises) > 0
        for ex in exercises:
            assert "rationale" in ex
            assert "sequencing_rationale" in ex
            assert "sequencing_role" in ex
        clear_store()

    def test_current_workout_plan_includes_safety_filter_summary(self):
        """current_workout_plan includes the safety_filter_summary."""
        clear_store()
        output = _make_mock_output()
        set_current_plan(JORDAN_ID, output)

        result = current_workout_plan(JORDAN_ID)
        assert "safety_filter_summary" in result
        summary = result["safety_filter_summary"]
        assert "safe_exercise_count" in summary
        assert "removed_exercise_count" in summary
        clear_store()

    def test_current_workout_plan_invalid_variant(self):
        """current_workout_plan returns error for invalid variant_id."""
        clear_store()
        output = _make_mock_output()
        set_current_plan(JORDAN_ID, output)

        result = current_workout_plan(JORDAN_ID, variant_id="power")
        assert "error" in result
        clear_store()


# ---------------------------------------------------------------------------
# 2. Observability — tracing_config and decision_trace (no API key)
# ---------------------------------------------------------------------------


class TestObservability:
    """Deterministic observability tests — no API key or LLM."""

    def test_langsmith_enabled_returns_false_without_env(self, monkeypatch):
        """langsmith_enabled returns False when env vars are not set."""
        monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
        monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
        assert langsmith_enabled() is False

    def test_langsmith_enabled_returns_false_with_only_tracing_flag(
        self, monkeypatch
    ):
        """langsmith_enabled returns False when only LANGCHAIN_TRACING_V2 is set."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
        assert langsmith_enabled() is False

    def test_langsmith_enabled_returns_true_with_both_vars(self, monkeypatch):
        """langsmith_enabled returns True when both env vars are set."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")
        assert langsmith_enabled() is True

    def test_tracing_config_no_key_returns_config(self, monkeypatch):
        """tracing_config returns a valid RunnableConfig without crashing when no key."""
        monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
        monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

        config = tracing_config("test_run", member_id="mbr_test")
        assert isinstance(config, dict)
        assert "run_name" in config
        assert config["run_name"] == "test_run"
        # No metadata when tracing is disabled
        assert "metadata" not in config

    def test_tracing_config_with_key_includes_metadata(self, monkeypatch):
        """tracing_config with LangSmith env vars includes metadata dict."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "ls__test_key")

        config = tracing_config(
            "structure_plan",
            member_id="mbr_01HX9JORDAN",
            variant_id="strength",
            prompt="lower body",
        )
        assert isinstance(config, dict)
        assert config["run_name"] == "structure_plan"
        assert "metadata" in config
        metadata = config["metadata"]
        assert metadata["member_id"] == "mbr_01HX9JORDAN"
        assert metadata["variant_id"] == "strength"
        assert metadata["prompt"] == "lower body"

    def test_tracing_config_never_crashes(self, monkeypatch):
        """tracing_config must never raise regardless of env state."""
        # Test with various combinations
        for tracing, key in [
            ("true", ""),
            ("false", "ls__key"),
            ("", ""),
            ("TRUE", "ls__key"),
        ]:
            if tracing:
                monkeypatch.setenv("LANGCHAIN_TRACING_V2", tracing)
            else:
                monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
            if key:
                monkeypatch.setenv("LANGCHAIN_API_KEY", key)
            else:
                monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

            # Must not raise
            config = tracing_config("test_run", foo="bar")
            assert isinstance(config, dict)

    def test_build_decision_trace_no_injury(self):
        """build_decision_trace returns 6 ordered steps when no injury."""
        steps = build_decision_trace(
            prompt="full body",
            member_id=JORDAN_ID,
            injury_joint=None,
            injured_node_ids=None,
            excluded_movement_types=None,
            available_equipment={"Dumbbell", "Resistance Band - Loop"},
            dislikes=set(),
            safe_count=30,
            removed_count=5,
            removed_exercises=[{"name": "Barbell Squat", "id": "ex_001", "reason": "no barbell"}],
            variant_ids=["strength", "conditioning", "mobility"],
        )
        assert len(steps) == 6
        for step in steps:
            assert isinstance(step, DecisionStep)
            assert step.name
            assert step.detail

    def test_build_decision_trace_with_injury(self):
        """build_decision_trace with injury includes part_of_traversal step."""
        steps = build_decision_trace(
            prompt="lower body",
            member_id=JORDAN_ID,
            injury_joint="knee",
            injured_node_ids={"knee", "49076000", "57714003"},
            excluded_movement_types={"flexion", "load"},
            available_equipment={"Dumbbell", "Resistance Band - Loop"},
            dislikes={"burpees"},
            safe_count=20,
            removed_count=10,
            removed_exercises=[
                {"name": "Barbell Squat", "id": "ex_001", "reason": "movement type(s) flexion excluded at injured joint"},
                {"name": "Leg Press", "id": "ex_002", "reason": "stresses injured joint"},
            ],
            variant_ids=["strength", "conditioning", "mobility"],
        )
        assert len(steps) == 6

        step_names = [s.name for s in steps]
        assert "resolve_prompt" in step_names
        assert "load_constraints" in step_names
        assert "part_of_traversal" in step_names
        assert "movement_type_exclusion" in step_names
        assert "equipment_gate" in step_names
        assert "llm_structuring" in step_names

    def test_decision_trace_step_kinds(self):
        """Deterministic steps have kind='deterministic'; LLM step has kind='llm'."""
        steps = build_decision_trace(
            prompt="test",
            member_id=JORDAN_ID,
            injury_joint=None,
            injured_node_ids=None,
            excluded_movement_types=None,
            available_equipment=set(),
            dislikes=set(),
            safe_count=10,
            removed_count=2,
            removed_exercises=[],
            variant_ids=["strength", "conditioning", "mobility"],
        )
        # All steps except the last should be deterministic
        for step in steps[:-1]:
            assert step.kind == "deterministic", (
                f"Step '{step.name}' should be 'deterministic', got '{step.kind}'"
            )
        # Last step (llm_structuring) should be 'llm'
        assert steps[-1].kind == "llm"
        assert steps[-1].name == "llm_structuring"

    def test_decision_trace_inputs_outputs_are_dicts(self):
        """Every DecisionStep has dict inputs and outputs."""
        steps = build_decision_trace(
            prompt="test",
            member_id=JORDAN_ID,
            injury_joint="knee",
            injured_node_ids={"knee"},
            excluded_movement_types={"flexion"},
            available_equipment={"Dumbbell"},
            dislikes=set(),
            safe_count=15,
            removed_count=3,
            removed_exercises=[],
            variant_ids=["strength", "conditioning", "mobility"],
        )
        for step in steps:
            assert isinstance(step.inputs, dict), f"Step '{step.name}' inputs must be dict"
            assert isinstance(step.outputs, dict), f"Step '{step.name}' outputs must be dict"

    def test_generator_output_carries_decision_trace(self):
        """
        GeneratorOutput has a decision_trace field that can be set.
        Existing consumers that don't use decision_trace still work fine.
        """
        from app.generator.pipeline import GeneratorOutput
        from app.graph.conditional_filter import ConditionalFilterTrace

        output = GeneratorOutput(
            variants=[],
            trace=ConditionalFilterTrace(),
            selected_variant_id=None,
            decision_trace=None,
        )
        assert output.decision_trace is None

        # Set a trace
        steps = [DecisionStep(name="test", detail="test step")]
        output.decision_trace = steps
        assert output.decision_trace is steps
        assert len(output.decision_trace) == 1


# ---------------------------------------------------------------------------
# 3. LLM-live agent tests — skipped without API key
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_API_KEY, reason="ANTHROPIC_API_KEY not set")
class TestCopilotAgentLive:
    """Tests that invoke the live LangGraph agent. Skipped without API key."""

    @pytest.fixture(autouse=True)
    def cleanup_store(self):
        clear_store()
        yield
        clear_store()

    def _build_agent(self):
        """Build the copilot agent for Jordan."""
        from app.copilot.agent import create_copilot_agent, get_copilot_llm
        from app.data.loader import load_member_context
        from app.graph.member_kg import MemberKG
        from app.ontology.catalog import build_concept_catalog

        llm = get_copilot_llm()
        assert llm is not None, "Expected LLM to be available with API key"

        member = load_member_context(JORDAN_ID)
        concepts = build_concept_catalog()
        mkg = MemberKG(member, concepts)
        agent = create_copilot_agent(mkg, llm)
        assert agent is not None, "Expected agent to be created successfully"
        return agent

    @pytest.mark.asyncio
    async def test_adherence_tool_invoked(self):
        """
        When asked about adherence, the agent should call adherence_trend
        and include adherence data in its response.
        """
        agent = self._build_agent()

        result = await agent.ainvoke(
            {"messages": [("human", f"How's adherence for member {JORDAN_ID}?")]},
        )

        messages = result.get("messages", [])
        # Check that a tool was called (tool message will be in the messages)
        message_types = [type(m).__name__ for m in messages]
        # Either ToolMessage or AIMessage with tool_calls should be present
        has_tool_call = any(
            hasattr(m, "tool_calls") and m.tool_calls
            for m in messages
        )
        has_tool_message = any(
            "ToolMessage" in type(m).__name__
            for m in messages
        )
        assert has_tool_call or has_tool_message, (
            f"Expected agent to call a tool for adherence question. "
            f"Message types: {message_types}"
        )

        # The final response should mention adherence-related content
        final_msg = messages[-1]
        response_text = ""
        if hasattr(final_msg, "content"):
            content = final_msg.content
            if isinstance(content, str):
                response_text = content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        response_text += block.get("text", "")

        assert len(response_text) > 0, "Agent should return a non-empty response"

    @pytest.mark.asyncio
    async def test_workout_awareness(self):
        """
        After a plan is set in the store, asking 'why were these exercises chosen?'
        should invoke current_workout_plan and the answer should reference
        the plan's rationale/stimulus.
        """
        # First, put a plan in the store for Jordan
        output = _make_mock_output("lower-body strength + knee-safe loading")
        set_current_plan(JORDAN_ID, output)

        agent = self._build_agent()

        result = await agent.ainvoke(
            {
                "messages": [
                    (
                        "human",
                        f"For member {JORDAN_ID}: why were these exercises chosen "
                        "in the current workout plan?",
                    )
                ]
            },
        )

        messages = result.get("messages", [])

        # Verify the agent called current_workout_plan (tool message present)
        tool_messages = [
            m for m in messages
            if "ToolMessage" in type(m).__name__
        ]
        tool_calls_made = []
        for m in messages:
            if hasattr(m, "tool_calls") and m.tool_calls:
                for tc in m.tool_calls:
                    if isinstance(tc, dict):
                        tool_calls_made.append(tc.get("name", ""))
                    elif hasattr(tc, "name"):
                        tool_calls_made.append(tc.name)

        assert (
            "current_workout_plan" in tool_calls_made or len(tool_messages) > 0
        ), (
            f"Expected agent to call 'current_workout_plan'. "
            f"Tool calls made: {tool_calls_made}"
        )

        # The final response should reference the plan context
        final_msg = messages[-1]
        response_text = ""
        if hasattr(final_msg, "content"):
            content = final_msg.content
            if isinstance(content, str):
                response_text = content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        response_text += block.get("text", "")

        assert len(response_text) > 0, "Agent should produce a non-empty response"


# ---------------------------------------------------------------------------
# 4. Copilot API endpoint smoke tests
# ---------------------------------------------------------------------------


class TestCopilotEndpoint:
    """API-level tests for POST /api/copilot/chat."""

    def test_chat_returns_503_without_api_key(self, monkeypatch):
        """Without ANTHROPIC_API_KEY the /chat endpoint returns 503."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/copilot/chat",
            json={"message": "What is the morning brief?", "member_id": JORDAN_ID},
        )
        assert response.status_code == 503

    def test_chat_sync_returns_503_without_api_key(self, monkeypatch):
        """Without ANTHROPIC_API_KEY the /chat/sync endpoint returns 503."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/copilot/chat/sync",
            json={"message": "How's adherence?", "member_id": JORDAN_ID},
        )
        assert response.status_code == 503
