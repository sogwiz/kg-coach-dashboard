"""
Phase 3 validation: Base Deterministic Safety Filter

Load-bearing invariants tested:
  1. Exercises stressing the knee are excluded when knee is injured
  2. Exercises requiring a barbell are excluded when barbell is not available
  3. Explicit excludes are removed
  4. Dislike matching removes exercises by name substring
  5. Substitution finds a structurally equivalent safe replacement by pattern+muscle
  6. No exercise appears in both safe and removed lists
  7. FilterTrace.safe_ids and removed_ids are consistent with safe/removed lists
  8. Exercises with no equipment pass the equipment gate even with empty available set
"""

from __future__ import annotations

import pytest

from app.data.loader import load_exercises
from app.graph.movement_kg import MovementKG
from app.graph.safety_filter import FilterTrace, safety_filter
from app.models.exercise import Exercise
from app.ontology.catalog import build_concept_catalog
from app.ontology.loader import load_snomed_anatomy


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
def all_exercises() -> list[Exercise]:
    return load_exercises()


@pytest.fixture(scope="module")
def knee_exercises(all_exercises) -> list[Exercise]:
    """Exercises that load the knee joint."""
    return [ex for ex in all_exercises if "knee" in ex.joints_loaded]


@pytest.fixture(scope="module")
def barbell_exercises(all_exercises) -> list[Exercise]:
    """Exercises that require a barbell."""
    return [ex for ex in all_exercises if "Barbell" in ex.equipment_required]


@pytest.fixture(scope="module")
def no_knee_exercises(all_exercises) -> list[Exercise]:
    """Exercises that do NOT load the knee (upper body, carries, etc.)"""
    return [ex for ex in all_exercises if "knee" not in ex.joints_loaded]


# ---------------------------------------------------------------------------
# Helper: build an all-equipment set so equipment gate never fires
# ---------------------------------------------------------------------------

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
    # Phase 11 hybrid equipment
    "Sled",
    "Rower",
    "Assault Bike",
    "Rope",
    "Tire",
}


# ---------------------------------------------------------------------------
# Invariant 1: Knee exercises excluded when knee is injured
# ---------------------------------------------------------------------------


class TestInjuryGate:
    def test_knee_exercises_removed_when_knee_injured(self, all_exercises, kg):
        """
        With knee injured, exercises that stress the knee joint must not
        appear in the safe list.
        """
        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=["knee"],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )

        # All safe exercises must NOT have knee in joints_loaded
        for ex in trace.safe:
            assert "knee" not in ex.joints_loaded, (
                f"Exercise '{ex.name}' loads the knee but is in safe list "
                f"when knee is injured."
            )

    def test_non_knee_exercises_remain_safe_when_knee_injured(
        self, no_knee_exercises, kg
    ):
        """
        Non-knee exercises should not be affected by a knee injury filter.
        """
        trace = safety_filter(
            candidates=no_knee_exercises,
            injured_joints=["knee"],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )

        # All candidates should be safe (none load the knee)
        assert len(trace.safe) == len(no_knee_exercises), (
            f"Expected all {len(no_knee_exercises)} non-knee exercises to be safe. "
            f"Got {len(trace.safe)} safe, {len(trace.removed)} removed."
        )

    def test_removed_reasons_mention_joint(self, all_exercises, kg):
        """Removal reasons for injury gate should name the joint."""
        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=["knee"],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )
        for ex, reason in trace.removed:
            if "knee" in ex.joints_loaded:
                # Not all removed exercises are removed for injury reasons
                # (could be equipment or dislikes), but injury-removed ones
                # should have "stresses" in the reason.
                assert "stresses" in reason.lower() or "joint" in reason.lower(), (
                    f"Expected injury-related reason for '{ex.name}', got: {reason}"
                )

    def test_no_injury_allows_knee_exercises(self, knee_exercises, kg):
        """
        With no injuries, knee exercises should not be filtered out by the
        injury gate.
        """
        trace = safety_filter(
            candidates=knee_exercises,
            injured_joints=[],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )
        # All knee exercises should be safe (no injury filter applied)
        assert len(trace.safe) == len(knee_exercises), (
            f"Expected all {len(knee_exercises)} knee exercises to be safe when "
            f"no injury. Got {len(trace.safe)} safe."
        )


# ---------------------------------------------------------------------------
# Invariant 2: Barbell exercises excluded when barbell not available
# ---------------------------------------------------------------------------


class TestEquipmentGate:
    def test_barbell_exercises_removed_when_barbell_unavailable(
        self, barbell_exercises, kg
    ):
        """
        Exercises requiring Barbell must be excluded when barbell is not
        in the available equipment set.
        """
        no_barbell = ALL_EQUIPMENT - {"Barbell"}
        trace = safety_filter(
            candidates=barbell_exercises,
            injured_joints=[],
            available_equipment=no_barbell,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )

        # All exercises here require Barbell, so all must be removed
        assert len(trace.safe) == 0, (
            f"Expected 0 safe exercises when barbell unavailable and all "
            f"candidates require barbell. Got {len(trace.safe)} safe."
        )
        assert len(trace.removed) == len(barbell_exercises), (
            f"Expected all {len(barbell_exercises)} barbell exercises removed. "
            f"Got {len(trace.removed)}."
        )

    def test_no_equipment_exercises_pass_with_empty_available(self, all_exercises, kg):
        """
        Exercises with no equipment_required should pass the equipment gate
        even if available_equipment is empty.
        """
        no_equip_exercises = [ex for ex in all_exercises if not ex.equipment_required]
        if not no_equip_exercises:
            pytest.skip("No exercises without equipment in catalog")

        trace = safety_filter(
            candidates=no_equip_exercises,
            injured_joints=[],
            available_equipment=set(),
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )

        assert len(trace.safe) == len(no_equip_exercises), (
            f"Expected all no-equipment exercises to be safe. "
            f"Got {len(trace.safe)} safe, {len(trace.removed)} removed."
        )

    def test_equipment_reason_mentions_missing_equipment(self, barbell_exercises, kg):
        """Equipment removal reason should name the missing equipment."""
        no_barbell = ALL_EQUIPMENT - {"Barbell"}
        trace = safety_filter(
            candidates=barbell_exercises,
            injured_joints=[],
            available_equipment=no_barbell,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )
        for ex, reason in trace.removed:
            assert "barbell" in reason.lower() or "equipment" in reason.lower(), (
                f"Expected equipment-related reason for '{ex.name}', got: {reason}"
            )


# ---------------------------------------------------------------------------
# Invariant 3: Explicit excludes
# ---------------------------------------------------------------------------


class TestExplicitExcludes:
    def test_explicit_exclude_removes_exercise(self, all_exercises, kg):
        """An exercise with its id in excluded_ids must be in the removed list."""
        target = all_exercises[0]
        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=[],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids={target.id},
            dislikes=set(),
            kg=kg,
        )

        assert target.id not in trace.safe_ids, (
            f"Exercise '{target.name}' should not be in safe list after explicit exclude."
        )
        assert target.id in trace.removed_ids, (
            f"Exercise '{target.name}' should be in removed list after explicit exclude."
        )

    def test_explicit_exclude_reason(self, all_exercises, kg):
        """Explicit exclude reason should say 'explicitly excluded'."""
        target = all_exercises[0]
        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=[],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids={target.id},
            dislikes=set(),
            kg=kg,
        )
        reasons = {ex.id: reason for ex, reason in trace.removed}
        assert "explicit" in reasons.get(target.id, "").lower(), (
            f"Expected 'explicitly excluded' reason, got: {reasons.get(target.id)}"
        )

    def test_empty_exclude_set_removes_nothing(self, all_exercises, kg):
        """Empty excluded_ids should not cause extra removals."""
        trace_with = safety_filter(
            candidates=all_exercises,
            injured_joints=[],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids={"nonexistent_id_xyz"},
            dislikes=set(),
            kg=kg,
        )
        trace_without = safety_filter(
            candidates=all_exercises,
            injured_joints=[],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )
        assert len(trace_with.safe) == len(trace_without.safe)


# ---------------------------------------------------------------------------
# Invariant 4: Dislike gate
# ---------------------------------------------------------------------------


class TestDislikeGate:
    def test_disliked_exercise_name_removed(self, all_exercises, kg):
        """Exercises whose name contains a dislike string should be removed."""
        # "Jumping Jack" should be removed if "Jumping Jack" is in dislikes
        jumping_jack = next(
            (ex for ex in all_exercises if "Jumping Jack" in ex.name), None
        )
        if jumping_jack is None:
            pytest.skip("Jumping Jack not in exercise catalog")

        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=[],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes={"Jumping Jack"},
            kg=kg,
        )

        assert jumping_jack.id not in trace.safe_ids, (
            "Jumping Jack should be removed when it is a dislike."
        )
        assert jumping_jack.id in trace.removed_ids, (
            "Jumping Jack should be in removed list."
        )

    def test_dislike_is_case_insensitive(self, all_exercises, kg):
        """Dislike matching should be case-insensitive."""
        jumping_jack = next(
            (ex for ex in all_exercises if "Jumping Jack" in ex.name), None
        )
        if jumping_jack is None:
            pytest.skip("Jumping Jack not in exercise catalog")

        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=[],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes={"jumping jack"},  # lowercase
            kg=kg,
        )

        assert jumping_jack.id not in trace.safe_ids

    def test_empty_dislikes_removes_nothing(self, all_exercises, kg):
        """Empty dislikes set should not remove anything via the dislike gate."""
        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=[],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )
        # With all equipment and no injuries/excludes/dislikes, all exercises safe
        assert len(trace.safe) == len(all_exercises)


# ---------------------------------------------------------------------------
# Invariant 5: Substitution finds equivalent by pattern+muscle
# ---------------------------------------------------------------------------


class TestSubstitution:
    def test_substitution_for_barbell_squat(self, all_exercises, kg):
        """
        When barbell squat exercises are excluded (barbell unavailable),
        the filter should find a dumbbell/kettlebell squat as a substitute.
        """
        barbell_squat_exercises = [
            ex for ex in all_exercises
            if "Barbell" in ex.equipment_required
            and "lower push - squat" in ex.movement_patterns
        ]

        if not barbell_squat_exercises:
            pytest.skip("No barbell squat exercises in catalog")

        no_barbell = ALL_EQUIPMENT - {"Barbell", "Plate", "Rack"}
        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=[],
            available_equipment=no_barbell,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )

        # The filter should have found substitutes for barbell squat exercises
        substituted_ids = {dropped.id for dropped, _, _ in trace.substitutions}
        barbell_squat_ids = {ex.id for ex in barbell_squat_exercises}
        overlap = substituted_ids & barbell_squat_ids

        # At least one barbell squat should have a substitute
        # (the goblet squat, KB squat, etc. should be available in the safe pool)
        assert len(overlap) > 0 or len(trace.substitutions) > 0, (
            f"Expected substitutions for barbell exercises. "
            f"Removed: {[(ex.name, r) for ex, r in trace.removed[:3]]}"
        )

    def test_substitute_is_from_safe_pool(self, all_exercises, kg):
        """Substitutes must be exercises that are in the safe pool."""
        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=["knee"],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )

        safe_ids = trace.safe_ids
        for dropped, substitute, rationale in trace.substitutions:
            assert substitute.id in safe_ids, (
                f"Substitute '{substitute.name}' is not in the safe pool! "
                f"Safe pool size: {len(safe_ids)}"
            )

    def test_substitute_has_same_primary_pattern(self, all_exercises, kg):
        """Substitutes should share the primary movement pattern."""
        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=["knee"],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )

        for dropped, substitute, rationale in trace.substitutions:
            if dropped.movement_patterns:
                primary = dropped.movement_patterns[0]
                assert primary in substitute.movement_patterns, (
                    f"Substitute '{substitute.name}' (patterns: {substitute.movement_patterns}) "
                    f"should share primary pattern '{primary}' with '{dropped.name}'"
                )


# ---------------------------------------------------------------------------
# Invariant 6 & 7: Consistency of FilterTrace
# ---------------------------------------------------------------------------


class TestFilterTraceConsistency:
    def test_no_exercise_in_both_safe_and_removed(self, all_exercises, kg):
        """An exercise must not appear in both safe and removed."""
        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=["knee"],
            available_equipment=ALL_EQUIPMENT - {"Barbell"},
            excluded_ids=set(),
            dislikes={"Jumping Jack"},
            kg=kg,
        )

        safe_ids = trace.safe_ids
        removed_ids = trace.removed_ids
        intersection = safe_ids & removed_ids

        assert len(intersection) == 0, (
            f"Exercises appear in both safe and removed: {intersection}"
        )

    def test_safe_plus_removed_equals_candidates(self, all_exercises, kg):
        """Every candidate must end up in either safe or removed (no losses)."""
        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=["knee"],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )

        candidate_ids = {ex.id for ex in all_exercises}
        accounted_ids = trace.safe_ids | trace.removed_ids

        assert candidate_ids == accounted_ids, (
            f"Some exercises unaccounted for. "
            f"Missing: {candidate_ids - accounted_ids}"
        )

    def test_safe_ids_property_matches_safe_list(self, all_exercises, kg):
        """FilterTrace.safe_ids should match {ex.id for ex in trace.safe}."""
        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=[],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )
        assert trace.safe_ids == {ex.id for ex in trace.safe}

    def test_removed_ids_property_matches_removed_list(self, all_exercises, kg):
        """FilterTrace.removed_ids should match {ex.id for ex, _ in trace.removed}."""
        trace = safety_filter(
            candidates=all_exercises,
            injured_joints=["knee"],
            available_equipment=ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )
        assert trace.removed_ids == {ex.id for ex, _ in trace.removed}
