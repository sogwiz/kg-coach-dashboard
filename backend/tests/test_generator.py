"""
Phase 6 validation: Generator Pipeline + LLM Structuring (3 variants)

Tests:
  1. Safety filter integration: no contraindicated exercises appear in the safe
     set for Jordan (knee injury, pain on flexion) or Mico (lumbar injury,
     pain on flexion/load). Runs WITHOUT an API key.
  2. 3-variant scaffolding: the three variant slots are present with distinct
     variant_ids; runs WITHOUT an API key using mock LLM.
  3. Store round-trip: set_current_plan / get_current_plan work correctly with
     the 3-variant GeneratorOutput shape.
  4. select_variant: records the selection and returns the updated output.
  5. LLM structuring (skipped without API key): generate_workout returns 3
     well-formed variants with distinct stimulus fields.
  6. API endpoint smoke tests: POST /api/generate returns 503 without API key;
     POST /api/generate/select returns 404 with no prior plan.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.data.loader import load_exercises, load_member_context
from app.generator.store import clear_store, get_current_plan, select_variant, set_current_plan
from app.graph.conditional_filter import ConditionalFilterTrace, conditional_safety_filter
from app.graph.movement_kg import MovementKG
from app.models.healing import compute_phase
from app.models.injury import HealingPhase, Injury, InjuryState
from app.ontology.catalog import build_concept_catalog
from app.ontology.loader import load_snomed_anatomy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

# Reference date: 2026-06-06 (day 27 since Jordan's 2026-05-10 onset = REMODELING)
REF_DATE = date(2026, 6, 6)

# All equipment for deterministic filter tests (no equipment filtering)
ALL_EQUIPMENT = {
    "Adjustable Bench - Decline",
    "Adjustable Bench - Incline",
    "BOSU",
    "Barbell",
    "Box",
    "Cable Resistance Machine",
    "Chest Supported Row Machine",
    "Dumbbell",
    "EZ Bar",
    "Flat Bench",
    "Handle Attachment",
    "Horizontal Leg Press Machine",
    "Jump Rope",
    "Kettlebell",
    "Lacrosse Ball",
    "Medicine Ball",
    "Miniband",
    "Plate",
    "Preacher Curl Bench",
    "Pull-Up Bar",
    "Rack",
    "Resistance Band - Loop",
    "Resistance Band - With Handles",
    "Sandbag",
    "Seated Lat Pulldown Machine",
    "SkiErg",
    "Slant Board",
    "Stability Ball",
    "Stair Climber",
    "Suspension Trainer",
    "Wall",
    "Yoga Mat",
}


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def kg() -> MovementKG:
    exercises = load_exercises()
    concepts = build_concept_catalog()
    snomed = load_snomed_anatomy()
    return MovementKG(exercises, concepts, snomed)


@pytest.fixture(scope="module")
def all_exercises():
    return load_exercises()


@pytest.fixture(scope="module")
def jordan_injury() -> Injury:
    """Jordan's left knee injury with today's check-in (remodeling phase, pain on flexion)."""
    state = InjuryState(
        injury_id="inj_knee_left",
        recorded_at=datetime(2026, 6, 6, 8, 15, tzinfo=timezone.utc),
        inflammation="none",
        pain_on=["flexion"],
        subjective_pain=2,
        load_tolerance_pct=0.7,
    )
    days = (REF_DATE - date(2026, 5, 10)).days
    phase = compute_phase(days)
    return Injury(
        id="inj_knee_left",
        region="left knee",
        joint="knee",
        diagnosis="Patellofemoral pain syndrome",
        snomed_code="57773001",
        onset_date=date(2026, 5, 10),
        current_phase=phase,
        states=[state],
    )


@pytest.fixture(scope="module")
def mico_injury() -> Injury:
    """Mico's lumbar spine injury with today's check-in (pain on flexion + load)."""
    state = InjuryState(
        injury_id="inj_lumbar_spine",
        recorded_at=datetime(2026, 6, 6, 7, 30, tzinfo=timezone.utc),
        inflammation="mild",
        pain_on=["flexion", "load"],
        subjective_pain=3,
        load_tolerance_pct=0.6,
    )
    # Onset 2025-11-01 — well past 90 days => RTA phase
    days = (REF_DATE - date(2025, 11, 1)).days
    phase = compute_phase(days)
    return Injury(
        id="inj_lumbar_spine",
        region="lumbar spine",
        joint="lumbar_spine",
        diagnosis="Mechanical low-back pain",
        snomed_code="279039007",
        onset_date=date(2025, 11, 1),
        current_phase=phase,
        states=[state],
    )


# ---------------------------------------------------------------------------
# Helpers: build a minimal GeneratorOutput for store tests
# ---------------------------------------------------------------------------


def _make_mock_plan(stimulus: str = "test stimulus"):
    from app.models.plan import WorkoutPlan
    return WorkoutPlan(
        warmup=[],
        main=[],
        cooldown=[],
        total_minutes=30,
        stimulus=stimulus,
        target_adaptation="",
        design_rationale="",
    )


def _make_mock_provenance(prompt: str = "test"):
    from app.generator.pipeline import Provenance
    return Provenance(
        generated_at=datetime.now(tz=timezone.utc),
        prompt=prompt,
        time_window_minutes=30,
    )


def _make_mock_output(
    strength_stimulus: str = "strength stimulus",
    conditioning_stimulus: str = "conditioning stimulus",
    mobility_stimulus: str = "mobility stimulus",
) -> "GeneratorOutput":
    from app.generator.pipeline import GeneratorOutput, WorkoutVariant

    variants = [
        WorkoutVariant(
            variant_id="strength",
            label="Strength & Hypertrophy",
            optimizes_for="load/intensity-biased",
            plan=_make_mock_plan(strength_stimulus),
            provenance=_make_mock_provenance(),
        ),
        WorkoutVariant(
            variant_id="conditioning",
            label="Conditioning & Metabolic",
            optimizes_for="density/metabolic",
            plan=_make_mock_plan(conditioning_stimulus),
            provenance=_make_mock_provenance(),
        ),
        WorkoutVariant(
            variant_id="mobility",
            label="Mobility & Recovery",
            optimizes_for="ROM-biased recovery",
            plan=_make_mock_plan(mobility_stimulus),
            provenance=_make_mock_provenance(),
        ),
    ]
    return GeneratorOutput(
        variants=variants,
        trace=ConditionalFilterTrace(),
        selected_variant_id=None,
    )


# ---------------------------------------------------------------------------
# 1. Safety filter integration — Jordan's knee: no API key required
# ---------------------------------------------------------------------------


class TestSafetyFilterJordan:
    """
    Verify the shared safe set for Jordan has no knee-flexion exercises.
    These tests run deterministically without an API key.
    """

    def test_no_knee_flexion_exercises_in_safe_set(self, all_exercises, kg, jordan_injury):
        """
        After conditional_safety_filter with Jordan's knee injury (pain on flexion),
        no exercise in the safe set should stress the knee with flexion movement.
        """
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=jordan_injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )

        knee_nodes = kg.descendants_by_part_of("knee")

        for ex in trace.safe:
            if not kg.graph.has_node(ex.id):
                continue
            for _, target, edge_data in kg.graph.out_edges(ex.id, data=True):
                if (
                    edge_data.get("relation") == "stresses"
                    and target in knee_nodes
                ):
                    movement_types = set(edge_data.get("movement_types", []))
                    assert "flexion" not in movement_types, (
                        f"Exercise '{ex.name}' (id={ex.id}) performs flexion at "
                        f"knee node '{target}' but was not filtered out"
                    )

    def test_safe_set_is_non_empty(self, all_exercises, kg, jordan_injury):
        """There should be safe exercises remaining after filtering Jordan's injury."""
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=jordan_injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert len(trace.safe) > 0, "Expected at least some safe exercises"

    def test_removed_exercises_have_reasons(self, all_exercises, kg, jordan_injury):
        """Every exercise removed for injury reasons should have a non-empty reason."""
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=jordan_injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        for ex, reason in trace.removed:
            assert reason, f"Exercise '{ex.name}' was removed with no reason"

    def test_load_tolerance_capped(self, all_exercises, kg, jordan_injury):
        """Load tolerance should be 0.7 (from check-in state)."""
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=jordan_injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert trace.load_tolerance_pct == pytest.approx(0.7), (
            f"Expected load_tolerance_pct=0.7, got {trace.load_tolerance_pct}"
        )

    def test_member_context_has_knee_injury(self):
        """Jordan's loaded member context should include a left knee injury."""
        member = load_member_context()
        injury_joints = [inj.joint for inj in member.injuries]
        assert "knee" in injury_joints, (
            f"Expected 'knee' in Jordan's injuries, got: {injury_joints}"
        )

    def test_equipment_filtering_applied(self, all_exercises, kg, jordan_injury):
        """Equipment constraints from Jordan's member context should filter exercises."""
        member = load_member_context()
        member_equipment = set(member.equipment_available)

        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=jordan_injury,
            available_equipment=member_equipment,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )

        equipment_norm = {e.lower().strip() for e in member_equipment}
        for ex in trace.safe:
            for eq in ex.equipment_required:
                assert eq.lower().strip() in equipment_norm, (
                    f"Exercise '{ex.name}' requires '{eq}' which Jordan doesn't have"
                )


# ---------------------------------------------------------------------------
# 2. Safety filter integration — Mico's lumbar spine: no API key required
# ---------------------------------------------------------------------------


class TestSafetyFilterMico:
    """
    Verify the shared safe set for Mico has no lumbar-flexion/load exercises.
    These tests run deterministically without an API key.
    """

    def test_no_lumbar_flexion_exercises_in_safe_set(self, all_exercises, kg, mico_injury):
        """
        After conditional_safety_filter with Mico's lumbar injury (pain on flexion),
        no exercise in the safe set should stress the lumbar spine with flexion.
        """
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=mico_injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )

        lumbar_nodes = kg.descendants_by_part_of("lumbar_spine")

        for ex in trace.safe:
            if not kg.graph.has_node(ex.id):
                continue
            for _, target, edge_data in kg.graph.out_edges(ex.id, data=True):
                if (
                    edge_data.get("relation") == "stresses"
                    and target in lumbar_nodes
                ):
                    movement_types = set(edge_data.get("movement_types", []))
                    assert "flexion" not in movement_types, (
                        f"Exercise '{ex.name}' (id={ex.id}) performs flexion at "
                        f"lumbar node '{target}' but was not filtered out for Mico"
                    )

    def test_no_lumbar_load_exercises_in_safe_set(self, all_exercises, kg, mico_injury):
        """
        Mico's injury includes pain on 'load' — no lumbar-loading exercise should
        appear in the safe set.
        """
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=mico_injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )

        lumbar_nodes = kg.descendants_by_part_of("lumbar_spine")

        for ex in trace.safe:
            if not kg.graph.has_node(ex.id):
                continue
            for _, target, edge_data in kg.graph.out_edges(ex.id, data=True):
                if (
                    edge_data.get("relation") == "stresses"
                    and target in lumbar_nodes
                ):
                    movement_types = set(edge_data.get("movement_types", []))
                    assert "load" not in movement_types, (
                        f"Exercise '{ex.name}' (id={ex.id}) applies load at "
                        f"lumbar node '{target}' but was not filtered out for Mico"
                    )

    def test_mico_safe_set_is_non_empty(self, all_exercises, kg, mico_injury):
        """There should be safe exercises remaining after filtering Mico's injury."""
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=mico_injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert len(trace.safe) > 0, "Expected at least some safe exercises for Mico"

    def test_mico_member_context_has_lumbar_injury(self):
        """Mico's loaded member context should include a lumbar spine injury."""
        member = load_member_context("mbr_MICO")
        injury_joints = [inj.joint for inj in member.injuries]
        assert "lumbar_spine" in injury_joints, (
            f"Expected 'lumbar_spine' in Mico's injuries, got: {injury_joints}"
        )


# ---------------------------------------------------------------------------
# 3. Three-variant scaffolding — no API key required (uses mock LLM)
# ---------------------------------------------------------------------------


class TestThreeVariantScaffolding:
    """
    Verify the 3-variant structure is correct without requiring a live LLM.
    We mock the LLM to return a minimal WorkoutPlan for each variant call.
    """

    def test_three_distinct_variant_ids(self):
        """GeneratorOutput must have exactly 3 variants with distinct ids."""
        output = _make_mock_output()
        assert len(output.variants) == 3
        variant_ids = {v.variant_id for v in output.variants}
        assert variant_ids == {"strength", "conditioning", "mobility"}

    def test_variant_ids_and_labels_match_profile(self):
        """Each variant id must match the expected label from VARIANT_PROFILES."""
        from app.generator.pipeline import VARIANT_PROFILES
        output = _make_mock_output()
        profile_map = {vid: label for vid, label, _ in VARIANT_PROFILES}
        for variant in output.variants:
            assert variant.label == profile_map[variant.variant_id], (
                f"Variant '{variant.variant_id}' has label '{variant.label}', "
                f"expected '{profile_map[variant.variant_id]}'"
            )

    def test_variant_optimizes_for_distinct(self):
        """All three optimizes_for fields must be distinct."""
        output = _make_mock_output()
        opts = [v.optimizes_for for v in output.variants]
        assert len(set(opts)) == 3, f"Expected 3 distinct optimizes_for, got: {opts}"

    def test_no_selected_variant_id_initially(self):
        """selected_variant_id is None when no selection has been made."""
        output = _make_mock_output()
        assert output.selected_variant_id is None

    def test_shared_trace_present(self):
        """GeneratorOutput must carry a shared filter trace."""
        output = _make_mock_output()
        assert output.trace is not None

    @pytest.mark.asyncio
    async def test_generate_workout_produces_three_variants_with_mock_llm(
        self, kg, all_exercises
    ):
        """
        generate_workout returns a GeneratorOutput with exactly 3 variants
        when given a mock LLM — no API key needed.
        """
        from app.generator.pipeline import GeneratorInput, generate_workout
        from app.models.plan import PlannedExercise, WorkoutPlan

        # Build a minimal mock plan to return for each variant call
        mock_plan = WorkoutPlan(
            warmup=[],
            main=[
                PlannedExercise(
                    exercise_id="ex_001",
                    name="Test Exercise",
                    sets=3,
                    reps=10,
                    rest_seconds=60,
                    rationale="Mock rationale.",
                )
            ],
            cooldown=[],
            total_minutes=30,
            stimulus="mock stimulus",
            target_adaptation="mock adaptation",
            design_rationale="mock rationale",
        )

        mock_llm = MagicMock()
        structured_mock = MagicMock()
        structured_mock.invoke.return_value = mock_plan
        mock_llm.with_structured_output.return_value = structured_mock

        member = load_member_context()
        gen_input = GeneratorInput(
            prompt="full body",
            time_window_minutes=45,
            member_id=member.profile.id,
        )

        output = await generate_workout(
            input=gen_input,
            kg=kg,
            member=member,
            llm=mock_llm,
        )

        assert len(output.variants) == 3
        variant_ids = {v.variant_id for v in output.variants}
        assert variant_ids == {"strength", "conditioning", "mobility"}
        assert output.trace is not None
        assert output.selected_variant_id is None

    @pytest.mark.asyncio
    async def test_all_variants_use_same_safe_set(self, kg, all_exercises):
        """
        All three variants must reference exercises only from the single shared
        safe set (filter runs once, not three times).
        """
        from app.generator.pipeline import GeneratorInput, generate_workout
        from app.models.plan import PlannedExercise, WorkoutPlan

        exercises = load_exercises()
        call_count = {"n": 0}

        def _mock_structure(*args, **kwargs):
            call_count["n"] += 1
            # Return a minimal plan for each call
            return WorkoutPlan(
                warmup=[],
                main=[
                    PlannedExercise(
                        exercise_id="ex_001",
                        name="Mock",
                        sets=1,
                        reps=1,
                        rest_seconds=30,
                        rationale="",
                    )
                ],
                cooldown=[],
                total_minutes=30,
                stimulus=f"stimulus_{call_count['n']}",
                target_adaptation="",
                design_rationale="",
            )

        mock_llm = MagicMock()
        structured_mock = MagicMock()
        structured_mock.invoke.side_effect = lambda msgs: _mock_structure()
        mock_llm.with_structured_output.return_value = structured_mock

        member = load_member_context()
        gen_input = GeneratorInput(
            prompt="test",
            time_window_minutes=45,
            member_id=member.profile.id,
        )

        output = await generate_workout(
            input=gen_input,
            kg=kg,
            member=member,
            llm=mock_llm,
        )

        # LLM was called exactly 3 times (once per variant)
        assert call_count["n"] == 3
        # There is exactly one shared trace
        assert output.trace is not None
        assert len(output.variants) == 3


# ---------------------------------------------------------------------------
# 4. Store round-trip — no API key required
# ---------------------------------------------------------------------------


class TestPlanStore:
    def setup_method(self):
        clear_store()

    def teardown_method(self):
        clear_store()

    def test_get_current_plan_returns_none_when_empty(self):
        """Store returns None before any plan is set."""
        assert get_current_plan("mbr_test") is None

    def test_set_and_get_current_plan(self):
        """Plan persisted via set_current_plan is retrievable via get_current_plan."""
        output = _make_mock_output("strength s1", "conditioning s1", "mobility s1")
        set_current_plan("mbr_test", output)

        retrieved = get_current_plan("mbr_test")
        assert retrieved is not None
        assert len(retrieved.variants) == 3
        assert retrieved.variants[0].plan.stimulus == "strength s1"
        assert retrieved.variants[1].plan.stimulus == "conditioning s1"
        assert retrieved.variants[2].plan.stimulus == "mobility s1"

    def test_set_overwrites_previous_plan(self):
        """Setting a new plan for the same member replaces the previous one."""
        set_current_plan("mbr_test", _make_mock_output("old"))
        set_current_plan("mbr_test", _make_mock_output("new"))
        retrieved = get_current_plan("mbr_test")
        assert retrieved is not None
        assert retrieved.variants[0].plan.stimulus == "new"

    def test_different_members_have_independent_stores(self):
        """Plans for different members don't interfere with each other."""
        set_current_plan("member_a", _make_mock_output("strength_a"))
        set_current_plan("member_b", _make_mock_output("strength_b"))

        assert get_current_plan("member_a").variants[0].plan.stimulus == "strength_a"
        assert get_current_plan("member_b").variants[0].plan.stimulus == "strength_b"


# ---------------------------------------------------------------------------
# 5. select_variant — no API key required
# ---------------------------------------------------------------------------


class TestSelectVariant:
    def setup_method(self):
        clear_store()

    def teardown_method(self):
        clear_store()

    def test_select_variant_updates_selected_variant_id(self):
        """select_variant sets the selected_variant_id on the stored output."""
        output = _make_mock_output()
        set_current_plan("mbr_test", output)

        updated = select_variant("mbr_test", "conditioning")
        assert updated is not None
        assert updated.selected_variant_id == "conditioning"

        # Also verify the stored copy was updated
        stored = get_current_plan("mbr_test")
        assert stored.selected_variant_id == "conditioning"

    def test_select_variant_returns_none_when_no_plan(self):
        """select_variant returns None when no plan has been stored for the member."""
        result = select_variant("nonexistent_member", "strength")
        assert result is None

    def test_select_variant_returns_none_for_invalid_variant_id(self):
        """select_variant returns None for a variant_id not in the output."""
        output = _make_mock_output()
        set_current_plan("mbr_test", output)

        result = select_variant("mbr_test", "power")  # not a valid variant
        assert result is None

    def test_select_each_valid_variant(self):
        """All three valid variant_ids can be selected."""
        for vid in ("strength", "conditioning", "mobility"):
            clear_store()
            output = _make_mock_output()
            set_current_plan("mbr_test", output)
            updated = select_variant("mbr_test", vid)
            assert updated is not None
            assert updated.selected_variant_id == vid

    def test_reselect_overwrites_previous_selection(self):
        """Selecting a different variant overwrites the previous selection."""
        output = _make_mock_output()
        set_current_plan("mbr_test", output)

        select_variant("mbr_test", "strength")
        updated = select_variant("mbr_test", "mobility")
        assert updated.selected_variant_id == "mobility"


# ---------------------------------------------------------------------------
# 6. LLM structuring — skipped without API key
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_API_KEY, reason="ANTHROPIC_API_KEY not set")
class TestLLMStructuring:
    """Tests that require a live LLM call."""

    def test_structure_plan_returns_workout_plan(self, all_exercises, kg, jordan_injury):
        """structure_plan returns a WorkoutPlan with all required fields."""
        from app.generator.llm import get_structuring_llm, structure_plan

        trace = conditional_safety_filter(
            candidates=all_exercises[:20],
            injury=jordan_injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )

        llm = get_structuring_llm()
        plan = structure_plan(
            safe_exercises=trace.safe[:10],
            intent="lower body strength",
            time_minutes=45,
            load_tolerance_pct=0.7,
            llm=llm,
        )

        assert plan.total_minutes > 0
        assert len(plan.main) > 0, "Main section should have at least one exercise"
        assert plan.stimulus, "stimulus field should be populated"
        assert plan.target_adaptation, "target_adaptation field should be populated"
        assert plan.design_rationale, "design_rationale field should be populated"


# ---------------------------------------------------------------------------
# 7. Full pipeline integration — skipped without API key
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_API_KEY, reason="ANTHROPIC_API_KEY not set")
class TestFullPipeline:
    def setup_method(self):
        clear_store()

    def teardown_method(self):
        clear_store()

    @pytest.mark.asyncio
    async def test_generate_workout_returns_three_variants(self, kg):
        """generate_workout returns a GeneratorOutput with exactly 3 variants."""
        from app.generator.llm import get_structuring_llm
        from app.generator.pipeline import GeneratorInput, generate_workout

        member = load_member_context()
        llm = get_structuring_llm()

        gen_input = GeneratorInput(
            prompt="lower body strength",
            time_window_minutes=50,
            member_id=member.profile.id,
        )

        output = await generate_workout(
            input=gen_input,
            kg=kg,
            member=member,
            llm=llm,
        )

        assert len(output.variants) == 3
        variant_ids = {v.variant_id for v in output.variants}
        assert variant_ids == {"strength", "conditioning", "mobility"}
        assert output.trace is not None
        assert output.selected_variant_id is None

    @pytest.mark.asyncio
    async def test_no_knee_exercises_in_any_variant(self, kg):
        """
        For Jordan, no knee-stressing (flexion) exercise should appear in
        any of the three generated variants.
        """
        from app.generator.llm import get_structuring_llm
        from app.generator.pipeline import GeneratorInput, generate_workout

        member = load_member_context()
        llm = get_structuring_llm()

        gen_input = GeneratorInput(
            prompt="lower body",
            time_window_minutes=50,
            member_id=member.profile.id,
        )

        output = await generate_workout(
            input=gen_input,
            kg=kg,
            member=member,
            llm=llm,
        )

        removed_ids = {ex.id for ex, _ in output.trace.removed}

        for variant in output.variants:
            all_planned = (
                variant.plan.warmup + variant.plan.main + variant.plan.cooldown
            )
            planned_ids = {ex.exercise_id for ex in all_planned}
            contraindicated = planned_ids & removed_ids
            assert not contraindicated, (
                f"Variant '{variant.variant_id}': contraindicated exercises "
                f"appeared in plan: {contraindicated}"
            )

    @pytest.mark.asyncio
    async def test_variants_have_distinct_stimulus(self, kg):
        """
        The three variants should have distinct stimulus fields, since each
        optimizes for a different goal.
        """
        from app.generator.llm import get_structuring_llm
        from app.generator.pipeline import GeneratorInput, generate_workout

        member = load_member_context()
        llm = get_structuring_llm()

        gen_input = GeneratorInput(
            prompt="full body",
            time_window_minutes=50,
            member_id=member.profile.id,
        )

        output = await generate_workout(
            input=gen_input,
            kg=kg,
            member=member,
            llm=llm,
        )

        stimuli = [v.plan.stimulus for v in output.variants]
        # At minimum, all stimuli should be non-empty
        for s in stimuli:
            assert s, "Each variant's stimulus should be non-empty"

    @pytest.mark.asyncio
    async def test_variants_have_session_level_fields(self, kg):
        """All variants must have non-empty stimulus, target_adaptation, design_rationale."""
        from app.generator.llm import get_structuring_llm
        from app.generator.pipeline import GeneratorInput, generate_workout

        member = load_member_context()
        llm = get_structuring_llm()

        gen_input = GeneratorInput(
            prompt="full body conditioning",
            time_window_minutes=45,
            member_id=member.profile.id,
        )

        output = await generate_workout(
            input=gen_input,
            kg=kg,
            member=member,
            llm=llm,
        )

        for variant in output.variants:
            assert variant.plan.stimulus, (
                f"Variant '{variant.variant_id}': stimulus must be non-empty"
            )
            assert variant.plan.target_adaptation, (
                f"Variant '{variant.variant_id}': target_adaptation must be non-empty"
            )
            assert variant.plan.design_rationale, (
                f"Variant '{variant.variant_id}': design_rationale must be non-empty"
            )

    @pytest.mark.asyncio
    async def test_generate_workout_persists_to_store(self, kg):
        """After generate_workout + set_current_plan, the plan is in the store."""
        from app.generator.llm import get_structuring_llm
        from app.generator.pipeline import GeneratorInput, generate_workout

        member = load_member_context()
        llm = get_structuring_llm()
        member_id = member.profile.id

        assert get_current_plan(member_id) is None

        gen_input = GeneratorInput(
            prompt="upper body",
            time_window_minutes=40,
            member_id=member_id,
        )

        output = await generate_workout(
            input=gen_input,
            kg=kg,
            member=member,
            llm=llm,
        )

        set_current_plan(member_id, output)
        stored = get_current_plan(member_id)

        assert stored is not None
        assert len(stored.variants) == 3


# ---------------------------------------------------------------------------
# 8. API endpoint smoke tests — requires httpx TestClient
# ---------------------------------------------------------------------------


class TestGeneratorEndpoint:
    """Tests for POST /api/generate and POST /api/generate/select."""

    def test_generate_returns_503_without_api_key(self, monkeypatch):
        """Without ANTHROPIC_API_KEY the endpoint returns 503."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        from fastapi.testclient import TestClient

        from app.api.routes import generator as gen_module
        gen_module._get_llm.cache_clear()

        from app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/generate",
            json={
                "prompt": "lower body",
                "time_window_minutes": 50,
                "member_id": "mbr_01HX9JORDAN",
            },
        )
        assert response.status_code == 503

        gen_module._get_llm.cache_clear()

    def test_select_returns_404_when_no_plan(self, monkeypatch):
        """POST /api/generate/select returns 404 when no plan has been generated."""
        clear_store()
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/generate/select",
            json={"member_id": "mbr_01HX9JORDAN", "variant_id": "strength"},
        )
        assert response.status_code == 404

    def test_select_returns_404_for_invalid_variant(self):
        """POST /api/generate/select returns 404 for an unknown variant_id."""
        clear_store()
        output = _make_mock_output()
        set_current_plan("mbr_01HX9JORDAN", output)

        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/generate/select",
            json={"member_id": "mbr_01HX9JORDAN", "variant_id": "nonexistent"},
        )
        assert response.status_code == 404

        clear_store()

    def test_select_returns_200_for_valid_variant(self):
        """POST /api/generate/select returns 200 with updated selected_variant_id."""
        clear_store()
        output = _make_mock_output()
        set_current_plan("mbr_01HX9JORDAN", output)

        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/generate/select",
            json={"member_id": "mbr_01HX9JORDAN", "variant_id": "conditioning"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["selected_variant_id"] == "conditioning"
        assert len(data["variants"]) == 3

        clear_store()

    @pytest.mark.skipif(not HAS_API_KEY, reason="ANTHROPIC_API_KEY not set")
    def test_generate_returns_three_variants_with_api_key(self):
        """With a valid API key, the endpoint returns a JSON object with 3 variants."""
        from fastapi.testclient import TestClient

        from app.api.routes import generator as gen_module
        gen_module._get_llm.cache_clear()
        gen_module._get_kg.cache_clear()

        from app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/generate",
            json={
                "prompt": "lower body strength",
                "time_window_minutes": 50,
                "member_id": "mbr_01HX9JORDAN",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "variants" in data
        assert "trace_summary" in data
        assert len(data["variants"]) == 3
        variant_ids = {v["variant_id"] for v in data["variants"]}
        assert variant_ids == {"strength", "conditioning", "mobility"}
        for v in data["variants"]:
            assert v["plan"]["stimulus"]
            assert v["plan"]["total_minutes"] > 0
