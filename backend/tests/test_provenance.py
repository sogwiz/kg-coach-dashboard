"""
Phase 12 — PROV-O Provenance Builder tests.

Assertions:
  1. build_provenance() returns a ProvODocument with PROV-O terms present.
  2. The prov:Activity has startedAtTime and endedAtTime.
  3. injury_state_used carries the check-in that drove filtering.
  4. filtered_out entries have reason + graph_path + injury_constraint.
  5. per_exercise entries have prov:wasDerivedFrom and prov:used.
  6. prov_document_to_dict() produces the expected top-level keys.
  7. An injury-filtered exercise has a non-empty graph_path.
  8. An equipment-filtered exercise has an empty graph_path and None injury_constraint.
  9. ProvODocument is correctly shaped (no KeyError on access).
 10. Integration: GeneratorOutput.prov_documents is populated end-to-end.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.data.loader import load_exercises
from app.generator.provenance import ProvODocument, build_provenance, prov_document_to_dict
from app.graph.conditional_filter import ConditionalFilterTrace, conditional_safety_filter
from app.graph.movement_kg import MovementKG
from app.models.injury import HealingPhase, Injury, InjuryState
from app.models.plan import PlannedExercise, WorkoutPlan
from app.ontology.catalog import build_concept_catalog
from app.ontology.loader import load_snomed_anatomy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REF_DATE = date(2026, 6, 6)  # 27 days since Jordan's 2026-05-10 onset = REMODELING

# Exercise IDs from test_conditional_filter.py (verified in catalog)
SQUAT_WITH_KNEE_FLEXION_ID = "00036a08-7c22-42e4-8fe5-323b53e31667"

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
    "Sled",
    "Rower",
    "Assault Bike",
    "Rope",
    "Tire",
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


def _make_knee_injury(
    onset_date: date = date(2026, 5, 10),
    states: list[InjuryState] | None = None,
    phase_override: HealingPhase | None = None,
) -> Injury:
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


def _make_minimal_plan(exercise_ids: list[str], exercise_names: list[str]) -> WorkoutPlan:
    """Build a minimal WorkoutPlan with one main exercise per id."""
    main = []
    for i, (ex_id, ex_name) in enumerate(zip(exercise_ids, exercise_names)):
        main.append(
            PlannedExercise(
                exercise_id=ex_id,
                name=ex_name,
                order=i + 1,
                sets=3,
                reps=10,
                rest_seconds=60,
                rationale=f"{ex_name} builds strength for this variant.",
                sequencing_rationale=f"{ex_name} placed first as the primary compound.",
                sequencing_role="compound",
            )
        )
    return WorkoutPlan(
        warmup=[],
        main=main,
        cooldown=[],
        total_minutes=45,
        stimulus="lower-body strength",
        target_adaptation="quad and glute hypertrophy",
        design_rationale="Focus on knee-safe compound movements.",
        sequence_logic="Compound first, accessories after.",
    )


@pytest.fixture(scope="module")
def trace_with_injury(kg, all_exercises) -> ConditionalFilterTrace:
    """Filter trace with knee injury, pain on flexion (today check-in)."""
    today_state = _make_state(
        recorded_at=datetime(2026, 6, 6, 8, 15, 0, tzinfo=timezone.utc),
        pain_on=["flexion"],
        load_tolerance_pct=0.7,
    )
    injury = _make_knee_injury(states=[today_state])
    return conditional_safety_filter(
        candidates=all_exercises,
        injury=injury,
        available_equipment=ALL_EQUIPMENT,
        excluded_ids=set(),
        dislikes=set(),
        kg=kg,
        reference_date=REF_DATE,
    )


@pytest.fixture(scope="module")
def trace_no_barbell(kg, all_exercises) -> ConditionalFilterTrace:
    """Filter trace without barbell (equipment gate)."""
    today_state = _make_state(
        recorded_at=datetime(2026, 6, 6, 8, 15, 0, tzinfo=timezone.utc),
        pain_on=[],
        load_tolerance_pct=0.8,
    )
    injury = _make_knee_injury(states=[today_state])
    no_barbell = ALL_EQUIPMENT - {"Barbell", "Rack"}
    return conditional_safety_filter(
        candidates=all_exercises,
        injury=injury,
        available_equipment=no_barbell,
        excluded_ids=set(),
        dislikes=set(),
        kg=kg,
        reference_date=REF_DATE,
    )


# ---------------------------------------------------------------------------
# Helper to build a prov document from a trace
# ---------------------------------------------------------------------------


def _build_prov_from_trace(trace: ConditionalFilterTrace, injury_joint: str = "knee") -> ProvODocument:
    """Build a ProvODocument from a filter trace, using a minimal plan."""
    # Take first 3 safe exercises for the plan
    safe = trace.safe[:3]
    plan = _make_minimal_plan(
        [ex.id for ex in safe],
        [ex.name for ex in safe],
    )
    started_at = datetime(2026, 6, 6, 8, 0, 0, tzinfo=timezone.utc)
    ended_at = datetime(2026, 6, 6, 8, 0, 5, tzinfo=timezone.utc)
    constraints = {
        "prompt": "lower body strength",
        "member_id": "mbr_01HX9JORDAN",
        "time_window_minutes": 45,
        "equipment_available": sorted(ALL_EQUIPMENT),
        "variant_id": "strength",
    }
    return build_provenance(
        plan=plan,
        trace=trace,
        constraints=constraints,
        timing=(started_at, ended_at),
        variant_id="strength",
        injury_joint=injury_joint,
    )


# ---------------------------------------------------------------------------
# Test 1: PROV-O terms are present in prov:Activity
# ---------------------------------------------------------------------------


def test_activity_has_prov_terms(trace_with_injury):
    doc = _build_prov_from_trace(trace_with_injury)
    activity = doc.activity
    assert "prov:startedAtTime" in activity, "prov:startedAtTime missing from Activity"
    assert "prov:endedAtTime" in activity, "prov:endedAtTime missing from Activity"
    assert "prov:wasAssociatedWith" in activity, "prov:wasAssociatedWith missing from Activity"
    assert "prov:type" in activity, "prov:type missing from Activity"
    assert activity["prov:type"] == "prov:Activity"


def test_activity_timing_is_iso_format(trace_with_injury):
    doc = _build_prov_from_trace(trace_with_injury)
    started = doc.activity["prov:startedAtTime"]
    ended = doc.activity["prov:endedAtTime"]
    # Should be parseable as ISO datetime
    datetime.fromisoformat(started)
    datetime.fromisoformat(ended)
    # ended should be >= started
    assert ended >= started


def test_activity_carries_prompt_and_member(trace_with_injury):
    doc = _build_prov_from_trace(trace_with_injury)
    assert doc.activity["prompt"] == "lower body strength"
    assert doc.activity["member_id"] == "mbr_01HX9JORDAN"
    assert doc.activity["time_window_minutes"] == 45
    assert doc.activity["variant_id"] == "strength"


# ---------------------------------------------------------------------------
# Test 2: Agent attribution
# ---------------------------------------------------------------------------


def test_agent_is_set(trace_with_injury):
    doc = _build_prov_from_trace(trace_with_injury)
    assert doc.agent, "agent should be non-empty"
    assert "kg-coach-dashboard" in doc.agent


# ---------------------------------------------------------------------------
# Test 3: injury_state_used carries PROV-O Entity with check-in data
# ---------------------------------------------------------------------------


def test_injury_state_used_present_when_injury(trace_with_injury):
    doc = _build_prov_from_trace(trace_with_injury)
    assert doc.injury_state_used is not None, "injury_state_used should be present"
    isu = doc.injury_state_used
    assert isu["prov:type"] == "prov:Entity"
    assert "prov:id" in isu
    assert "recorded_at" in isu
    # Check-in had pain on flexion
    assert "flexion" in isu["pain_on"]
    assert isu["load_tolerance_pct"] == pytest.approx(0.7)


def test_injury_state_used_none_when_no_states(kg, all_exercises):
    """No check-in → trace.injury_state_used should still be set (stale fallback)
    but if injury has no states at all, injury_state_used is None."""
    injury_no_states = _make_knee_injury(states=[])
    trace = conditional_safety_filter(
        candidates=all_exercises,
        injury=injury_no_states,
        available_equipment=ALL_EQUIPMENT,
        excluded_ids=set(),
        dislikes=set(),
        kg=kg,
        reference_date=REF_DATE,
    )
    # No states → injury_state_used should be None
    assert trace.injury_state_used is None
    doc = _build_prov_from_trace(trace)
    assert doc.injury_state_used is None


# ---------------------------------------------------------------------------
# Test 4: filtered_out entries have reason + graph_path + injury_constraint
# ---------------------------------------------------------------------------


def test_filtered_out_has_required_fields(trace_with_injury):
    doc = _build_prov_from_trace(trace_with_injury)
    assert len(doc.filtered_out) > 0, "Should have filtered-out exercises"
    for entry in doc.filtered_out:
        assert "exercise_id" in entry
        assert "exercise_name" in entry
        assert "reason" in entry
        assert "graph_path" in entry
        assert "injury_constraint" in entry
        assert "prov:type" in entry
        assert entry["prov:type"] == "prov:Entity"


def test_injury_filtered_out_has_graph_path_and_constraint(trace_with_injury):
    """Exercises removed due to injury exclusion have a non-empty graph_path
    and a non-None injury_constraint."""
    doc = _build_prov_from_trace(trace_with_injury)
    injury_entries = [
        e for e in doc.filtered_out
        if e.get("injury_constraint") is not None
    ]
    assert len(injury_entries) > 0, "Should have at least one injury-filtered exercise"
    for entry in injury_entries:
        assert len(entry["graph_path"]) > 0, (
            f"graph_path should be non-empty for injury exclusion: {entry['exercise_name']}"
        )
        # graph_path should start with the injured joint slug
        assert entry["graph_path"][0] == "knee", (
            f"First node in graph_path should be 'knee': {entry['graph_path']}"
        )


# ---------------------------------------------------------------------------
# Test 5: per_exercise entries have prov:wasDerivedFrom and prov:used
# ---------------------------------------------------------------------------


def test_per_exercise_prov_terms(trace_with_injury):
    doc = _build_prov_from_trace(trace_with_injury)
    assert len(doc.per_exercise) > 0, "Should have at least one planned exercise"
    for ex_entry in doc.per_exercise:
        assert "prov:wasDerivedFrom" in ex_entry, f"Missing prov:wasDerivedFrom in {ex_entry}"
        assert "prov:used" in ex_entry, f"Missing prov:used in {ex_entry}"
        assert "prov:type" in ex_entry
        assert ex_entry["prov:type"] == "prov:Entity"
        assert "why" in ex_entry, "Missing 'why' (rationale) in per_exercise entry"
        assert "sequencing_role" in ex_entry
        assert "sequencing_rationale" in ex_entry


def test_per_exercise_wasDerivedFrom_points_to_pool(trace_with_injury):
    """prov:wasDerivedFrom should reference the safe candidate pool entity."""
    doc = _build_prov_from_trace(trace_with_injury)
    for ex_entry in doc.per_exercise:
        derived_from = ex_entry["prov:wasDerivedFrom"]
        assert "safe_candidate_pool" in derived_from, (
            f"prov:wasDerivedFrom should reference the safe pool: {derived_from}"
        )


# ---------------------------------------------------------------------------
# Test 6: prov_document_to_dict() produces expected top-level keys
# ---------------------------------------------------------------------------


def test_prov_document_to_dict_shape(trace_with_injury):
    doc = _build_prov_from_trace(trace_with_injury)
    d = prov_document_to_dict(doc)
    required_keys = {
        "prov:Activity",
        "prov:wasAssociatedWith",
        "injury_state_used",
        "healing_phase",
        "prov:hadMember_per_exercise",
        "filtered_out",
    }
    for key in required_keys:
        assert key in d, f"Key '{key}' missing from prov_document_to_dict output"


def test_prov_document_to_dict_roundtrip(trace_with_injury):
    """prov_document_to_dict output should be JSON-serialisable."""
    import json
    doc = _build_prov_from_trace(trace_with_injury)
    d = prov_document_to_dict(doc)
    # Should not raise
    serialised = json.dumps(d, default=str)
    assert serialised  # non-empty


# ---------------------------------------------------------------------------
# Test 7: injury-filtered exercise has non-empty graph_path (dedicated test)
# ---------------------------------------------------------------------------


def test_squat_filtered_out_with_graph_path(trace_with_injury):
    """The squat (knee flexion) should be in filtered_out with a graph path
    showing the knee part-of traversal."""
    doc = _build_prov_from_trace(trace_with_injury)
    filtered_ids = {e["exercise_id"] for e in doc.filtered_out}
    # The squat with knee flexion should be excluded
    assert SQUAT_WITH_KNEE_FLEXION_ID in filtered_ids, (
        f"Squat with knee flexion ({SQUAT_WITH_KNEE_FLEXION_ID}) "
        f"should be in filtered_out"
    )
    squat_entry = next(e for e in doc.filtered_out if e["exercise_id"] == SQUAT_WITH_KNEE_FLEXION_ID)
    assert squat_entry["graph_path"], "Squat should have a non-empty graph_path"
    assert squat_entry["injury_constraint"] is not None


# ---------------------------------------------------------------------------
# Test 8: equipment-filtered exercise has empty graph_path + None injury_constraint
# ---------------------------------------------------------------------------


def test_barbell_exercise_filtered_by_equipment(trace_no_barbell):
    """When barbell is not in equipment, barbell exercises should be filtered
    without injury_constraint (pure equipment gate)."""
    doc = _build_prov_from_trace(trace_no_barbell)
    equipment_filtered = [
        e for e in doc.filtered_out
        if e.get("injury_constraint") is None
        and "equipment" in e.get("reason", "").lower()
    ]
    assert len(equipment_filtered) > 0, (
        "Should have at least one equipment-filtered exercise with "
        "injury_constraint=None"
    )
    for entry in equipment_filtered:
        assert entry["graph_path"] == [], (
            f"graph_path should be empty for equipment-filtered: {entry['exercise_name']}"
        )


# ---------------------------------------------------------------------------
# Test 9: ProvODocument structure (no KeyError on access)
# ---------------------------------------------------------------------------


def test_prov_document_attributes_accessible(trace_with_injury):
    doc = _build_prov_from_trace(trace_with_injury)
    # Access all attributes — should not raise
    _ = doc.activity
    _ = doc.agent
    _ = doc.injury_state_used
    _ = doc.healing_phase
    _ = doc.per_exercise
    _ = doc.filtered_out

    # Basic type checks
    assert isinstance(doc.activity, dict)
    assert isinstance(doc.agent, str)
    assert isinstance(doc.per_exercise, list)
    assert isinstance(doc.filtered_out, list)


# ---------------------------------------------------------------------------
# Test 10: Integration — GeneratorOutput.prov_documents populated (unit level)
# ---------------------------------------------------------------------------


def test_generator_output_prov_structure(trace_with_injury):
    """
    Simulate what the pipeline does: build prov_documents for each variant
    from the same trace, and verify the dict is keyed by variant_id.
    """
    from app.generator.provenance import prov_document_to_dict
    safe = trace_with_injury.safe[:3]
    plan = _make_minimal_plan([ex.id for ex in safe], [ex.name for ex in safe])
    started_at = datetime(2026, 6, 6, 8, 0, 0, tzinfo=timezone.utc)
    ended_at = datetime(2026, 6, 6, 8, 0, 5, tzinfo=timezone.utc)

    prov_documents = {}
    for variant_id in ["strength", "conditioning", "mobility"]:
        constraints = {
            "prompt": "lower body strength",
            "member_id": "mbr_01HX9JORDAN",
            "time_window_minutes": 45,
            "equipment_available": sorted(ALL_EQUIPMENT),
            "variant_id": variant_id,
        }
        doc = build_provenance(
            plan=plan,
            trace=trace_with_injury,
            constraints=constraints,
            timing=(started_at, ended_at),
            variant_id=variant_id,
            injury_joint="knee",
        )
        prov_documents[variant_id] = prov_document_to_dict(doc)

    assert set(prov_documents.keys()) == {"strength", "conditioning", "mobility"}
    for variant_id, prov_dict in prov_documents.items():
        assert "prov:Activity" in prov_dict
        assert prov_dict["prov:Activity"]["variant_id"] == variant_id
        assert "filtered_out" in prov_dict
        assert "prov:hadMember_per_exercise" in prov_dict
