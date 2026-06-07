"""
Phase 5 validation: Dynamic Conditional Safety Filter

Tests cover:
  1. Acute phase excludes all load and impact exercises
  2. "pain on flexion" excludes squats (knee flexion) but allows extension-only exercises
  3. "pain on extension" excludes extension-only exercises but allows squats
  4. Load tolerance 0.5 is propagated in the trace
  5. No check-in today → uses most recent state with stale_check_in=True
  6. Phase override by coach takes precedence over computed phase
  7. ConditionalFilterTrace.safe and removed are disjoint
  8. Equipment gate still fires for missing equipment
  9. Explicit excludes still work
  10. Dislikes still work
"""

from __future__ import annotations

import warnings
from datetime import date, datetime, timezone

import pytest

from app.data.loader import load_exercises
from app.graph.conditional_filter import ConditionalFilterTrace, conditional_safety_filter
from app.graph.movement_kg import MovementKG
from app.models.healing import PHASE_RESTRICTIONS
from app.models.injury import HealingPhase, Injury, InjuryState
from app.ontology.catalog import build_concept_catalog
from app.ontology.loader import load_snomed_anatomy

# ---------------------------------------------------------------------------
# Known exercise IDs from exercise_movements.json (verified against catalog)
# ---------------------------------------------------------------------------

# Kettlebell Goblet Cyclist Squat: knee=[flexion, load]
SQUAT_WITH_KNEE_FLEXION_ID = "00036a08-7c22-42e4-8fe5-323b53e31667"

# One-Kettlebell Hamstring Walkout: knee=[extension]
HAMSTRING_WALKOUT_ID = "0732c6eb-2275-4af3-8276-9bb8be2aa12d"

# High Plank Bird Dog: knee=[extension] — bodyweight, no knee flexion
HIGH_PLANK_BIRD_DOG_ID = "01f5a2bb-ecf7-4168-92b3-35bd78592e26"

# Reference date: 2026-06-06 (27 days after Jordan's 2026-05-10 onset = REMODELING)
REF_DATE = date(2026, 6, 6)

# All equipment set (same as test_safety_filter.py)
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
# Fixtures
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


def _make_injury(
    onset_date: date = date(2026, 5, 10),
    states: list[InjuryState] | None = None,
    phase_override: HealingPhase | None = None,
) -> Injury:
    """Helper: build a test Injury for the left knee."""
    from app.models.healing import compute_phase
    days = (REF_DATE - onset_date).days
    phase = phase_override or compute_phase(days)
    return Injury(
        id="inj_knee_left",
        region="left knee",
        joint="knee",
        diagnosis="Patellofemoral pain syndrome",
        snomed_code="57773001",
        onset_date=onset_date,
        current_phase=phase,
        phase_override=phase_override,
        states=states or [],
    )


def _make_state(
    recorded_at: datetime,
    pain_on: list | None = None,
    load_tolerance_pct: float = 0.7,
    inflammation: str = "none",
    subjective_pain: int = 2,
) -> InjuryState:
    return InjuryState(
        injury_id="inj_knee_left",
        recorded_at=recorded_at,
        inflammation=inflammation,  # type: ignore[arg-type]
        pain_on=pain_on or [],
        subjective_pain=subjective_pain,
        load_tolerance_pct=load_tolerance_pct,
    )


# ---------------------------------------------------------------------------
# Scenario 1: Acute phase excludes load and impact exercises
# ---------------------------------------------------------------------------


class TestAcutePhaseExclusions:
    """Acute phase = days 0-6 since onset."""

    def _acute_injury(self) -> Injury:
        # Onset same day as ref_date → day 0 → acute
        return _make_injury(onset_date=REF_DATE)

    def test_acute_load_exercises_excluded(self, all_exercises, kg):
        """Exercises with knee=[load] must be excluded in acute phase."""
        injury = self._acute_injury()
        # acute state: no explicit check-in, relies on phase restrictions
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )

        acute_restrictions = PHASE_RESTRICTIONS[HealingPhase.ACUTE]
        excluded_types = set(acute_restrictions["excluded_movement_types"])

        for ex in trace.safe:
            # Get this exercise's movement types at the knee
            if kg.graph.has_node(ex.id):
                for _, target, edge_data in kg.graph.out_edges(ex.id, data=True):
                    if (
                        edge_data.get("relation") == "stresses"
                        and "knee" in target
                    ):
                        movement_types = set(edge_data.get("movement_types", []))
                        overlap = movement_types & excluded_types
                        assert not overlap, (
                            f"Exercise '{ex.name}' is safe but performs "
                            f"{overlap} at knee during acute phase"
                        )

    def test_acute_phase_restrictions_applied_in_trace(self, all_exercises, kg):
        """ConditionalFilterTrace.phase_restrictions_applied should reflect ACUTE."""
        injury = self._acute_injury()
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert trace.phase_restrictions_applied == PHASE_RESTRICTIONS[HealingPhase.ACUTE]

    def test_acute_load_tolerance_is_zero(self, all_exercises, kg):
        """Load tolerance must be 0.0 in acute phase (no loading)."""
        injury = self._acute_injury()
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert trace.load_tolerance_pct == 0.0


# ---------------------------------------------------------------------------
# Scenario 2: Pain on flexion — squats excluded, extension-only exercises safe
# ---------------------------------------------------------------------------


class TestPainOnFlexion:
    """
    "pain on flexion" → exclude any exercise doing flexion at the knee.

    Squat (knee=[flexion, load]) → excluded
    Hamstring Walkout (knee=[extension]) → safe
    """

    def _injury_with_flexion_pain(self) -> Injury:
        state = _make_state(
            recorded_at=datetime(2026, 6, 6, 8, 15, tzinfo=timezone.utc),
            pain_on=["flexion"],
            load_tolerance_pct=0.7,
        )
        return _make_injury(states=[state])

    def test_squat_excluded_with_pain_on_flexion(self, all_exercises, kg):
        """Squat with knee:flexion must be excluded when pain on flexion."""
        injury = self._injury_with_flexion_pain()
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert SQUAT_WITH_KNEE_FLEXION_ID not in trace.safe_ids, (
            "Goblet Squat (knee:flexion) should be excluded when pain on flexion"
        )
        assert SQUAT_WITH_KNEE_FLEXION_ID in trace.removed_ids

    def test_hamstring_walkout_safe_with_pain_on_flexion(self, all_exercises, kg):
        """Hamstring Walkout (knee:extension only) should be safe when pain on flexion."""
        injury = self._injury_with_flexion_pain()
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        # Hamstring Walkout requires Kettlebell + Yoga Mat — included in ALL_EQUIPMENT
        assert HAMSTRING_WALKOUT_ID in trace.safe_ids, (
            "Hamstring Walkout (knee:extension only) should be safe when pain on flexion"
        )

    def test_removal_reason_mentions_flexion(self, all_exercises, kg):
        """Removal reason for pain-on-flexion exclusions should mention 'flexion'."""
        injury = self._injury_with_flexion_pain()
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        removed_reasons = {ex.id: reason for ex, reason in trace.removed}
        if SQUAT_WITH_KNEE_FLEXION_ID in removed_reasons:
            reason = removed_reasons[SQUAT_WITH_KNEE_FLEXION_ID]
            assert "flexion" in reason.lower(), (
                f"Expected 'flexion' in removal reason, got: {reason}"
            )

    def test_injury_state_used_is_today_state(self, all_exercises, kg):
        """ConditionalFilterTrace.injury_state_used should be today's state."""
        injury = self._injury_with_flexion_pain()
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert trace.injury_state_used is not None
        assert trace.injury_state_used.recorded_at.date() == REF_DATE


# ---------------------------------------------------------------------------
# Scenario 3: Pain on extension — extension exercises excluded, squats safe
# ---------------------------------------------------------------------------


class TestPainOnExtension:
    """
    "pain on extension" → exclude any exercise doing extension at the knee.

    Hamstring Walkout (knee=[extension]) → excluded
    Goblet Squat (knee=[flexion, load]) → excluded too in remodeling (load allowed)
    Use High Plank Bird Dog (knee=[extension]) for a clean extension-only test.
    """

    def _injury_with_extension_pain(self) -> Injury:
        state = _make_state(
            recorded_at=datetime(2026, 6, 6, 8, 0, tzinfo=timezone.utc),
            pain_on=["extension"],
            load_tolerance_pct=0.7,
        )
        return _make_injury(states=[state])

    def test_hamstring_walkout_excluded_with_pain_on_extension(self, all_exercises, kg):
        """Hamstring Walkout (knee:extension) excluded when pain on extension."""
        injury = self._injury_with_extension_pain()
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert HAMSTRING_WALKOUT_ID not in trace.safe_ids, (
            "Hamstring Walkout (knee:extension) should be excluded with pain on extension"
        )

    def test_high_plank_bird_dog_excluded_with_pain_on_extension(self, all_exercises, kg):
        """High Plank Bird Dog (knee:extension) excluded when pain on extension."""
        injury = self._injury_with_extension_pain()
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert HIGH_PLANK_BIRD_DOG_ID not in trace.safe_ids, (
            "High Plank Bird Dog (knee:extension only) should be excluded with pain on extension"
        )

    def test_squats_can_be_safe_without_flexion_pain(self, all_exercises, kg):
        """
        In remodeling phase with pain on extension only (not flexion),
        the goblet squat (knee:flexion,load) should NOT be excluded by
        the extension pain rule.

        Note: load is allowed in remodeling phase by phase restrictions.
        """
        injury = self._injury_with_extension_pain()
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        # Goblet Squat has knee:[flexion, load]
        # Remodeling allows load (max_load_tolerance=0.80)
        # Extension pain only excludes extension — flexion is still allowed
        # So the goblet squat should be in the safe pool
        assert SQUAT_WITH_KNEE_FLEXION_ID in trace.safe_ids, (
            "Goblet Squat (knee:flexion,load) should be safe with pain on extension only "
            "(remodeling phase allows load; extension pain doesn't block flexion)"
        )


# ---------------------------------------------------------------------------
# Scenario 4: Load tolerance propagated in trace
# ---------------------------------------------------------------------------


class TestLoadTolerancePropagation:
    def test_load_tolerance_from_state_capped_by_phase(self, all_exercises, kg):
        """
        Effective load tolerance = min(state.load_tolerance_pct, phase.max_load_tolerance).
        In remodeling phase (max=0.80), state 0.5 → effective 0.5.
        """
        state = _make_state(
            recorded_at=datetime(2026, 6, 6, 8, tzinfo=timezone.utc),
            pain_on=[],
            load_tolerance_pct=0.5,
        )
        injury = _make_injury(states=[state])
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert trace.load_tolerance_pct == pytest.approx(0.5)

    def test_load_tolerance_phase_cap_applies(self, all_exercises, kg):
        """
        When state.load_tolerance_pct > phase maximum, phase cap applies.
        In subacute phase (max=0.30), state 0.8 → effective 0.30.
        """
        # Onset 10 days ago → subacute
        onset = date(2026, 5, 27)  # 10 days before REF_DATE
        state = _make_state(
            recorded_at=datetime(2026, 6, 6, 8, tzinfo=timezone.utc),
            pain_on=[],
            load_tolerance_pct=0.8,
        )
        injury = _make_injury(onset_date=onset, states=[state])
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert trace.load_tolerance_pct == pytest.approx(0.30, abs=0.01)

    def test_no_state_uses_phase_max_tolerance(self, all_exercises, kg):
        """
        When no check-in exists, effective_load_tol = phase max.
        In remodeling (max=0.80), trace.load_tolerance_pct should be 0.80.
        """
        injury = _make_injury(states=[])
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        phase_max = PHASE_RESTRICTIONS[HealingPhase.REMODELING]["max_load_tolerance"]
        assert trace.load_tolerance_pct == pytest.approx(phase_max)


# ---------------------------------------------------------------------------
# Scenario 5: No check-in today → stale state with warning
# ---------------------------------------------------------------------------


class TestStaleCheckIn:
    def test_stale_flag_when_no_checkin_today(self, all_exercises, kg):
        """When most recent state is not from today, stale_check_in must be True."""
        yesterday_state = _make_state(
            recorded_at=datetime(2026, 6, 5, 8, 0, tzinfo=timezone.utc),  # yesterday
            pain_on=["flexion"],
        )
        injury = _make_injury(states=[yesterday_state])

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            trace = conditional_safety_filter(
                candidates=all_exercises,
                injury=injury,
                available_equipment=ALL_EQUIPMENT,
                excluded_ids=set(),
                dislikes=set(),
                kg=kg,
                reference_date=REF_DATE,
            )

        assert trace.stale_check_in is True

    def test_warning_emitted_when_no_checkin_today(self, all_exercises, kg):
        """A UserWarning should be emitted when using a stale state."""
        yesterday_state = _make_state(
            recorded_at=datetime(2026, 6, 5, 8, 0, tzinfo=timezone.utc),
            pain_on=[],
        )
        injury = _make_injury(states=[yesterday_state])

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            conditional_safety_filter(
                candidates=all_exercises,
                injury=injury,
                available_equipment=ALL_EQUIPMENT,
                excluded_ids=set(),
                dislikes=set(),
                kg=kg,
                reference_date=REF_DATE,
            )

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) > 0, "Expected UserWarning for stale check-in"

    def test_stale_state_still_applies_restrictions(self, all_exercises, kg):
        """Even a stale state's pain_on restrictions should be applied."""
        yesterday_state = _make_state(
            recorded_at=datetime(2026, 6, 5, 8, 0, tzinfo=timezone.utc),
            pain_on=["flexion"],
        )
        injury = _make_injury(states=[yesterday_state])

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            trace = conditional_safety_filter(
                candidates=all_exercises,
                injury=injury,
                available_equipment=ALL_EQUIPMENT,
                excluded_ids=set(),
                dislikes=set(),
                kg=kg,
                reference_date=REF_DATE,
            )

        # Stale pain-on-flexion state should still exclude the squat
        assert SQUAT_WITH_KNEE_FLEXION_ID not in trace.safe_ids

    def test_no_states_at_all_no_stale_flag(self, all_exercises, kg):
        """When there are no states at all, stale_check_in should be False."""
        injury = _make_injury(states=[])
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert trace.stale_check_in is False


# ---------------------------------------------------------------------------
# Scenario 6: Phase override
# ---------------------------------------------------------------------------


class TestPhaseOverride:
    def test_coach_override_to_acute_applies_strict_rules(self, all_exercises, kg):
        """
        Phase override to ACUTE should apply acute restrictions even if computed
        phase would be REMODELING (day 27).
        """
        injury = _make_injury(phase_override=HealingPhase.ACUTE)
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        # Acute load tolerance is 0.0
        assert trace.load_tolerance_pct == 0.0

    def test_coach_override_to_rta_is_permissive(self, all_exercises, kg):
        """
        Phase override to RTA should allow full load tolerance (1.0)
        and no movement-type exclusions at phase level.
        """
        # Onset 1 day ago → would normally be ACUTE
        injury = _make_injury(
            onset_date=date(2026, 6, 5),
            phase_override=HealingPhase.RETURN_TO_ACTIVITY,
        )
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        # RTA max load tolerance = 1.0
        assert trace.load_tolerance_pct == pytest.approx(1.0)

    def test_phase_restrictions_in_trace_match_override(self, all_exercises, kg):
        """phase_restrictions_applied must reflect the overridden phase."""
        injury = _make_injury(phase_override=HealingPhase.SUBACUTE)
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert trace.phase_restrictions_applied == PHASE_RESTRICTIONS[HealingPhase.SUBACUTE]


# ---------------------------------------------------------------------------
# Inherited base filter gates still function
# ---------------------------------------------------------------------------


class TestBaseGatesStillWork:
    def _no_pain_injury(self) -> Injury:
        state = _make_state(
            recorded_at=datetime(2026, 6, 6, 8, 0, tzinfo=timezone.utc),
            pain_on=[],
            load_tolerance_pct=1.0,
        )
        return _make_injury(states=[state])

    def test_equipment_gate_still_removes_exercises(self, all_exercises, kg):
        """Equipment gate: exercises requiring missing equipment are removed."""
        injury = self._no_pain_injury()
        no_barbell = ALL_EQUIPMENT - {"Barbell"}
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=no_barbell,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        barbell_exercises = [ex for ex in all_exercises if "Barbell" in ex.equipment_required]
        for ex in barbell_exercises:
            assert ex.id not in trace.safe_ids, (
                f"Barbell exercise '{ex.name}' should be excluded without barbell"
            )

    def test_explicit_exclude_still_works(self, all_exercises, kg):
        """Explicit excludes are removed regardless of injury state."""
        injury = self._no_pain_injury()
        target = all_exercises[0]
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids={target.id},
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert target.id not in trace.safe_ids
        assert target.id in trace.removed_ids

    def test_dislikes_still_work(self, all_exercises, kg):
        """Dislike filtering still removes exercises by name substring."""
        injury = self._no_pain_injury()
        jumping_jack = next(
            (ex for ex in all_exercises if "Jumping Jack" in ex.name), None
        )
        if jumping_jack is None:
            pytest.skip("Jumping Jack not in catalog")

        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes={"Jumping Jack"},
            kg=kg,
            reference_date=REF_DATE,
        )
        assert jumping_jack.id not in trace.safe_ids


# ---------------------------------------------------------------------------
# Trace consistency
# ---------------------------------------------------------------------------


class TestTraceConsistency:
    def test_safe_and_removed_disjoint(self, all_exercises, kg):
        """No exercise may appear in both safe and removed."""
        state = _make_state(
            recorded_at=datetime(2026, 6, 6, 8, tzinfo=timezone.utc),
            pain_on=["flexion", "load"],
        )
        injury = _make_injury(states=[state])
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        intersection = trace.safe_ids & trace.removed_ids
        assert len(intersection) == 0, (
            f"Exercises in both safe and removed: {intersection}"
        )

    def test_all_candidates_accounted_for(self, all_exercises, kg):
        """safe + removed must account for every candidate."""
        injury = _make_injury()
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        candidate_ids = {ex.id for ex in all_exercises}
        accounted_ids = trace.safe_ids | trace.removed_ids
        assert candidate_ids == accounted_ids

    def test_conditional_filter_trace_is_instance_of_filter_trace(
        self, all_exercises, kg
    ):
        """ConditionalFilterTrace is a subtype of FilterTrace."""
        from app.graph.safety_filter import FilterTrace

        injury = _make_injury()
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        assert isinstance(trace, FilterTrace)

    def test_substitute_is_from_safe_pool(self, all_exercises, kg):
        """Substitutes must be drawn from the safe pool."""
        state = _make_state(
            recorded_at=datetime(2026, 6, 6, 8, tzinfo=timezone.utc),
            pain_on=["flexion"],
        )
        injury = _make_injury(states=[state])
        trace = conditional_safety_filter(
            candidates=all_exercises,
            injury=injury,
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
            reference_date=REF_DATE,
        )
        safe_ids = trace.safe_ids
        for dropped, substitute, rationale in trace.substitutions:
            assert substitute.id in safe_ids, (
                f"Substitute '{substitute.name}' not in safe pool"
            )
