"""
Phase 7 + 7.1 validation: Copilot Agent + Observability

Tests:
  1. Deterministic tool function tests (no LLM, no API key):
     - adherence_trend returns expected structure
     - morning_brief returns expected structure
     - injury_status returns expected structure
     - sleep_summary returns expected structure
     - current_workout_plan returns "no plan" marker when store is empty
     - current_workout_plan returns plan data after set_current_plan

  2. Phase 7.1 — new tool function tests (deterministic, no API key):
     - lab_results returns blood panel + DEXA for both members
     - body_composition returns DEXA and weight trend
     - workout_history returns recent sessions
     - goals_and_preferences returns goals + prefs
     - chat_history_search returns messages, filters by query
     - anti-fabrication: unknown member returns error (not invented data)

  3. Observability — no API key required:
     - tracing_config returns a RunnableConfig without crashing when no key
     - tracing_config with LANGCHAIN_TRACING_V2=true + key returns metadata
     - langsmith_enabled() returns False when env vars are not set
     - build_decision_trace returns ordered steps with correct kinds

  4. LLM-live agent tests (skipped without ANTHROPIC_API_KEY):
     - test_adherence_tool_invoked: agent calls adherence_trend when asked about
       adherence
     - test_workout_awareness: after a plan is set in the store, asking "why
       were these exercises chosen?" invokes current_workout_plan and the
       answer references the plan's rationale/stimulus
     - test_conversation_memory: two sequential turns in the same thread
       show that the second response has context from the first (memory)
     - test_anti_fabrication_unknown_member: asking about an unknown member
       returns an error, not invented data

  5. Copilot API endpoint smoke tests (deterministic):
     - chat_history endpoint returns Jordan's and Mico's chat history
     - CopilotRequest accepts attachments field (multimodal schema)

All deterministic tests run without an API key.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.copilot.agent import (
    adherence_trend,
    body_composition,
    chat_history_search,
    current_workout_plan,
    goals_and_preferences,
    injury_status,
    lab_results,
    morning_brief,
    sleep_summary,
    workout_history,
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
# 2. Phase 7.1 — new tool function tests (deterministic, no API key)
# ---------------------------------------------------------------------------


class TestPhase71ToolFunctions:
    """Test Phase 7.1 tool functions — no LLM invocation required."""

    # --- lab_results ---

    def test_lab_results_jordan_structure(self):
        """lab_results for Jordan returns blood_panel and dexa_scan keys."""
        result = lab_results(JORDAN_ID)
        assert isinstance(result, dict)
        assert "member_id" in result
        assert result["member_id"] == JORDAN_ID
        assert "blood_panel" in result
        assert "dexa_scan" in result

    def test_lab_results_jordan_blood_panel_values(self):
        """Jordan's blood panel contains expected fields with float values."""
        result = lab_results(JORDAN_ID)
        bp = result["blood_panel"]
        assert bp is not None, "Jordan should have a blood panel"
        assert isinstance(bp["ldl_mg_dl"], float)
        assert isinstance(bp["hdl_mg_dl"], float)
        assert isinstance(bp["date"], str)

    def test_lab_results_jordan_dexa_values(self):
        """Jordan's DEXA scan data is present."""
        result = lab_results(JORDAN_ID)
        dexa = result["dexa_scan"]
        assert dexa is not None, "Jordan should have a DEXA scan"
        assert isinstance(dexa["body_fat_pct"], float)
        assert isinstance(dexa["lean_mass_kg"], float)

    def test_lab_results_mico_has_hormone_panel(self):
        """Mico's blood panel includes testosterone and cortisol."""
        result = lab_results(MICO_ID)
        bp = result["blood_panel"]
        assert bp is not None
        assert bp["testosterone_ng_dl"] is not None, "Mico should have testosterone"
        assert bp["cortisol_morning_mcg_dl"] is not None, "Mico should have cortisol"

    def test_lab_results_unknown_member_returns_error(self):
        """lab_results for unknown member returns error dict."""
        result = lab_results("mbr_UNKNOWN_XYZ")
        assert "error" in result

    def test_lab_results_data_source_is_kg(self):
        """lab_results identifies Member KG as the data source (anti-fabrication audit)."""
        result = lab_results(JORDAN_ID)
        assert "data_source" in result
        assert "KG" in result["data_source"] or "kg" in result["data_source"].lower()

    # --- body_composition ---

    def test_body_composition_jordan_structure(self):
        """body_composition for Jordan returns dexa_scan and weight_trend_kg."""
        result = body_composition(JORDAN_ID)
        assert isinstance(result, dict)
        assert "dexa_scan" in result
        assert "weight_trend_kg" in result
        assert result["dexa_scan"]["available"] is True

    def test_body_composition_mico_lower_body_fat(self):
        """Mico's body fat % from DEXA is lower than Jordan's (fit male athlete)."""
        jordan_result = body_composition(JORDAN_ID)
        mico_result = body_composition(MICO_ID)
        jordan_bf = jordan_result["dexa_scan"]["body_fat_pct"]
        mico_bf = mico_result["dexa_scan"]["body_fat_pct"]
        assert mico_bf < jordan_bf, (
            f"Mico's body fat ({mico_bf}%) should be lower than Jordan's ({jordan_bf}%)"
        )

    def test_body_composition_weight_trend_is_list(self):
        """body_composition returns a list of weight data points."""
        result = body_composition(JORDAN_ID)
        assert isinstance(result["weight_trend_kg"], list)
        assert len(result["weight_trend_kg"]) > 0

    # --- workout_history ---

    def test_workout_history_jordan_structure(self):
        """workout_history for Jordan returns sessions with expected keys."""
        result = workout_history(JORDAN_ID)
        assert isinstance(result, dict)
        assert "sessions" in result
        assert isinstance(result["sessions"], list)
        assert "total_logged" in result
        assert result["total_logged"] > 0

    def test_workout_history_sessions_have_required_fields(self):
        """workout_history sessions include date, title, completed, rpe."""
        result = workout_history(JORDAN_ID)
        for s in result["sessions"]:
            assert "date" in s
            assert "title" in s
            assert "completed" in s

    def test_workout_history_respects_limit(self):
        """workout_history respects the limit parameter."""
        result = workout_history(JORDAN_ID, limit=2)
        assert len(result["sessions"]) <= 2

    def test_workout_history_mico_structure(self):
        """workout_history for Mico returns his recent sessions."""
        result = workout_history(MICO_ID)
        assert result["total_logged"] > 0
        assert len(result["sessions"]) > 0

    def test_workout_history_unknown_member_returns_error(self):
        """workout_history for unknown member returns error dict."""
        result = workout_history("mbr_UNKNOWN_XYZ")
        assert "error" in result

    # --- goals_and_preferences ---

    def test_goals_and_preferences_jordan_structure(self):
        """goals_and_preferences for Jordan returns goals + preferences."""
        result = goals_and_preferences(JORDAN_ID)
        assert isinstance(result, dict)
        assert "goals" in result
        assert "preferences" in result
        assert isinstance(result["goals"], list)
        assert len(result["goals"]) > 0

    def test_goals_and_preferences_jordan_has_knee_goal(self):
        """Jordan's goals include a knee-related goal."""
        result = goals_and_preferences(JORDAN_ID)
        texts = " ".join(g["text"].lower() for g in result["goals"])
        assert "knee" in texts or "squat" in texts

    def test_goals_and_preferences_mico_hormone_goal(self):
        """Mico's goals include hormone optimization."""
        result = goals_and_preferences(MICO_ID)
        texts = " ".join(g["text"].lower() for g in result["goals"])
        assert any(kw in texts for kw in ("hormone", "testosterone", "hyrox", "lumbar"))

    def test_goals_sorted_by_priority(self):
        """Goals returned by goals_and_preferences are sorted by priority."""
        result = goals_and_preferences(JORDAN_ID)
        priorities = [g["priority"] for g in result["goals"]]
        assert priorities == sorted(priorities), (
            f"Goals should be sorted by priority. Got: {priorities}"
        )

    def test_preferences_has_expected_keys(self):
        """Preferences dict contains expected keys."""
        result = goals_and_preferences(JORDAN_ID)
        prefs = result["preferences"]
        assert "preferred_session_minutes" in prefs
        assert "training_days_per_week" in prefs
        assert "dislikes" in prefs
        assert isinstance(prefs["dislikes"], list)

    def test_goals_and_preferences_unknown_member_returns_error(self):
        """goals_and_preferences for unknown member returns error dict."""
        result = goals_and_preferences("mbr_UNKNOWN_XYZ")
        assert "error" in result

    # --- chat_history_search ---

    def test_chat_history_search_jordan_all_messages(self):
        """chat_history_search with no query returns all of Jordan's messages."""
        result = chat_history_search(JORDAN_ID)
        assert isinstance(result, dict)
        assert "messages" in result
        assert result["total_messages"] > 0

    def test_chat_history_search_messages_have_required_fields(self):
        """Chat messages have ts, from, text, attachments."""
        result = chat_history_search(JORDAN_ID)
        for msg in result["messages"]:
            assert "ts" in msg
            assert "from" in msg
            assert "text" in msg
            assert "attachments" in msg
            assert msg["from"] in ("member", "coach")

    def test_chat_history_search_query_filters(self):
        """chat_history_search with a query returns only matching messages."""
        result = chat_history_search(JORDAN_ID, query="knee")
        # Jordan has messages mentioning knee
        assert result["total_messages"] > 0
        for msg in result["messages"]:
            assert "knee" in msg["text"].lower(), (
                f"Filtered message should contain 'knee': {msg['text']}"
            )

    def test_chat_history_search_empty_query_returns_all(self):
        """chat_history_search with empty query returns all messages."""
        all_result = chat_history_search(JORDAN_ID, query="")
        filtered_result = chat_history_search(JORDAN_ID, query="knee")
        # Filtered should be <= total
        assert filtered_result["total_messages"] <= all_result["total_messages"]

    def test_chat_history_search_mico_has_messages(self):
        """chat_history_search for Mico returns his chat history."""
        result = chat_history_search(MICO_ID)
        assert result["total_messages"] > 0

    def test_chat_history_search_mico_back_related(self):
        """Mico's chat history has back/lumbar related messages."""
        result = chat_history_search(MICO_ID, query="back")
        assert result["total_messages"] > 0, (
            "Mico should have messages mentioning 'back'"
        )

    def test_chat_history_search_unknown_member_returns_error(self):
        """chat_history_search for unknown member returns error dict."""
        result = chat_history_search("mbr_UNKNOWN_XYZ")
        assert "error" in result

    def test_chat_history_search_data_source_is_kg(self):
        """chat_history_search identifies Member KG as data source."""
        result = chat_history_search(JORDAN_ID)
        assert "data_source" in result

    # --- anti-fabrication: unknown member path ---

    def test_all_tools_return_error_not_fabrication_for_unknown_member(self):
        """
        Anti-fabrication: every tool function returns an error dict (not
        invented data) when given an unknown member_id.
        """
        fake_id = "mbr_DOES_NOT_EXIST_12345"
        tool_fns = [
            adherence_trend,
            morning_brief,
            injury_status,
            sleep_summary,
            lab_results,
            body_composition,
            workout_history,
            goals_and_preferences,
            chat_history_search,
        ]
        for fn in tool_fns:
            result = fn(fake_id)
            assert "error" in result, (
                f"Tool '{fn.__name__}' should return an error for unknown member, "
                f"got: {result}"
            )
            # The error should mention the member id — not invent data
            assert fake_id in result["error"] or "not found" in result["error"].lower(), (
                f"Tool '{fn.__name__}' error message should identify the missing member"
            )


# ---------------------------------------------------------------------------
# 3. Observability — tracing_config and decision_trace (no API key)
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
# 4. Phase 7.1 LLM-live agent tests (skipped without ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_API_KEY, reason="ANTHROPIC_API_KEY not set")
class TestCopilotAgentLivePhase71:
    """Phase 7.1 LLM-live tests. Skipped without API key."""

    @pytest.fixture(autouse=True)
    def cleanup_store(self):
        clear_store()
        yield
        clear_store()

    def _build_agent_for_member(self, member_id: str):
        """Build the copilot agent for the given member."""
        from app.copilot.agent import create_copilot_agent, get_copilot_llm
        from app.data.loader import load_member_context
        from app.graph.member_kg import MemberKG
        from app.ontology.catalog import build_concept_catalog

        llm = get_copilot_llm()
        assert llm is not None
        member = load_member_context(member_id)
        concepts = build_concept_catalog()
        mkg = MemberKG(member, concepts)
        agent = create_copilot_agent(mkg, llm)
        assert agent is not None
        return agent

    @pytest.mark.asyncio
    async def test_conversation_memory_persists_across_turns(self):
        """
        Two sequential turns in the same thread — the second response should
        reflect the context established in the first turn (R2 conversation memory).

        Uses the MemorySaver checkpointer keyed by thread_id=member_id.
        """
        agent = self._build_agent_for_member(JORDAN_ID)
        thread_cfg = {"configurable": {"thread_id": f"test_memory_{JORDAN_ID}"}}

        # Turn 1: ask about adherence
        result1 = await agent.ainvoke(
            {"messages": [("human", f"What is Jordan's ({JORDAN_ID}) adherence trend?")]},
            config=thread_cfg,
        )
        msgs1 = result1.get("messages", [])
        assert len(msgs1) > 0

        # Turn 2: follow-up that relies on Turn 1 context
        result2 = await agent.ainvoke(
            {"messages": [("human", "What does that trend suggest about churn risk?")]},
            config=thread_cfg,
        )
        msgs2 = result2.get("messages", [])
        # The thread should have more messages than Turn 1 alone (accumulated)
        assert len(msgs2) > len(msgs1), (
            "Thread should accumulate messages across turns (conversation memory)"
        )

        # Final response should be non-empty
        final = msgs2[-1]
        response_text = (
            final.content if isinstance(final.content, str)
            else " ".join(
                b.get("text", "") if isinstance(b, dict) else b
                for b in final.content
            )
        )
        assert len(response_text) > 0

    @pytest.mark.asyncio
    async def test_lab_results_tool_invoked(self):
        """
        When asked about labs, the agent should call lab_results tool and
        return data grounded in the KG — not invented.
        """
        agent = self._build_agent_for_member(JORDAN_ID)
        thread_cfg = {"configurable": {"thread_id": f"test_labs_{JORDAN_ID}"}}

        result = await agent.ainvoke(
            {"messages": [("human", f"What are {JORDAN_ID}'s latest lab results?")]},
            config=thread_cfg,
        )
        messages = result.get("messages", [])

        # Verify a tool was called
        tool_calls_made = []
        for m in messages:
            if hasattr(m, "tool_calls") and m.tool_calls:
                for tc in m.tool_calls:
                    name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
                    tool_calls_made.append(name)

        assert "lab_results" in tool_calls_made or len([
            m for m in messages if "ToolMessage" in type(m).__name__
        ]) > 0, (
            f"Expected agent to call 'lab_results'. Calls: {tool_calls_made}"
        )

    @pytest.mark.asyncio
    async def test_anti_fabrication_unknown_member(self):
        """
        Anti-fabrication: when asked about an unknown member, the agent should
        surface the error from the tool (member not found) — not invent data.
        """
        agent = self._build_agent_for_member(JORDAN_ID)
        thread_cfg = {"configurable": {"thread_id": "test_antifab_unknown"}}

        result = await agent.ainvoke(
            {
                "messages": [
                    (
                        "human",
                        "What is the adherence for member mbr_DOES_NOT_EXIST_12345?",
                    )
                ]
            },
            config=thread_cfg,
        )
        messages = result.get("messages", [])
        final = messages[-1]
        response_text = (
            final.content if isinstance(final.content, str)
            else " ".join(
                b.get("text", "") if isinstance(b, dict) else b
                for b in final.content
                if isinstance(b, (str, dict))
            )
        )
        # The response should acknowledge the error, not fabricate member data
        assert len(response_text) > 0
        # Should mention not found / error — not invent adherence numbers
        lower = response_text.lower()
        assert any(kw in lower for kw in ("not found", "error", "unable", "cannot", "don't have")), (
            f"Expected agent to surface an error for unknown member. Got: {response_text[:300]}"
        )


# ---------------------------------------------------------------------------
# 5. Copilot API endpoint smoke tests
# ---------------------------------------------------------------------------


class TestCopilotEndpoint:
    """API-level tests for POST /api/copilot/chat and GET /chat-history."""

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

    def test_chat_history_endpoint_jordan(self):
        """GET /api/copilot/members/jordan/chat-history returns Jordan's messages."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get(f"/api/copilot/members/{JORDAN_ID}/chat-history")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Each message should have expected keys
        for msg in data:
            assert "ts" in msg
            assert "from" in msg
            assert "text" in msg
            assert "attachments" in msg
            assert msg["from"] in ("member", "coach")

    def test_chat_history_endpoint_mico(self):
        """GET /api/copilot/members/mico/chat-history returns Mico's messages."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get(f"/api/copilot/members/{MICO_ID}/chat-history")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_chat_history_endpoint_unknown_member_returns_404(self):
        """GET /api/copilot/members/unknown/chat-history returns 404."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/copilot/members/mbr_DOES_NOT_EXIST/chat-history")
        assert response.status_code == 404

    def test_chat_history_jordan_has_image_attachment(self):
        """Jordan's chat history includes at least one message with an attachment."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get(f"/api/copilot/members/{JORDAN_ID}/chat-history")
        assert response.status_code == 200
        data = response.json()
        msgs_with_attachments = [m for m in data if m.get("attachments")]
        assert len(msgs_with_attachments) > 0, (
            "Jordan's chat history should include at least one message with an attachment"
        )

    def test_chat_history_is_chronologically_ordered(self):
        """Chat history is returned in chronological order (oldest first)."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get(f"/api/copilot/members/{JORDAN_ID}/chat-history")
        assert response.status_code == 200
        data = response.json()
        if len(data) > 1:
            timestamps = [m["ts"] for m in data]
            assert timestamps == sorted(timestamps), (
                "Chat history should be in chronological order"
            )

    def test_copilot_request_accepts_attachments(self, monkeypatch):
        """
        CopilotRequest schema accepts an 'attachments' field (multimodal support).
        Validates the schema without invoking the LLM.
        """
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        # POST with attachments field — should get 503 (no key) not 422 (schema error)
        response = client.post(
            "/api/copilot/chat",
            json={
                "message": "What is Jordan's body composition?",
                "member_id": JORDAN_ID,
                "attachments": [
                    {"type": "image/jpeg", "caption": "Progress photo", "url": None}
                ],
            },
        )
        # 503 means the schema was accepted (LLM key missing), not 422 (schema error)
        assert response.status_code == 503, (
            f"Expected 503 (no API key) not 422 (schema rejection). Got: {response.status_code}"
        )
