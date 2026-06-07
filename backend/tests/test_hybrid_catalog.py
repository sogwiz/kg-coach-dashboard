"""
Phase 11 validation: Hybrid exercise catalog loads and validates.

Tests:
  1. Hybrid exercises load via load_exercises() — base + hybrid merged.
  2. All hybrid exercises conform to the 14-field Exercise schema.
  3. Hybrid exercises have movement annotations (joint_movements populated).
  4. Safety filter still gates Mico's lumbar and Jordan's knee on hybrid exercises.
  5. Catalog now contains new hybrid equipment concepts (Sled, Rower, etc.).
  6. Hybrid exercise count is exactly 20 (hyb-001 through hyb-020).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.data.loader import load_exercises
from app.graph.conditional_filter import conditional_safety_filter
from app.graph.movement_kg import MovementKG
from app.models.healing import compute_phase
from app.models.injury import HealingPhase, Injury, InjuryState
from app.ontology.catalog import build_concept_catalog
from app.ontology.loader import load_snomed_anatomy


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def exercises():
    return load_exercises()


@pytest.fixture(scope="module")
def hybrid_exercises(exercises):
    """Return only exercises whose id starts with 'hyb-'."""
    return [ex for ex in exercises if ex.id.startswith("hyb-")]


@pytest.fixture(scope="module")
def kg(exercises):
    catalog = build_concept_catalog()
    snomed = load_snomed_anatomy()
    return MovementKG(exercises, catalog, snomed)


# ---------------------------------------------------------------------------
# 1. Load and count
# ---------------------------------------------------------------------------


class TestHybridLoad:
    def test_exercises_exceed_50_with_hybrid(self, exercises):
        """load_exercises() returns more than 50 records after hybrid merge."""
        assert len(exercises) > 50, (
            f"Expected > 50 exercises after hybrid merge, got {len(exercises)}"
        )

    def test_hybrid_exercise_count(self, hybrid_exercises):
        """Exactly 20 hybrid exercises (hyb-001 through hyb-020)."""
        assert len(hybrid_exercises) == 20, (
            f"Expected 20 hybrid exercises, got {len(hybrid_exercises)}"
        )

    def test_base_exercises_still_present(self, exercises):
        """The original 50 base exercises are still present."""
        base_exercises = [ex for ex in exercises if not ex.id.startswith("hyb-")]
        assert len(base_exercises) == 50, (
            f"Expected 50 base exercises, got {len(base_exercises)}"
        )


# ---------------------------------------------------------------------------
# 2. Schema validation (14 fields)
# ---------------------------------------------------------------------------


class TestHybridSchema:
    _REQUIRED_FIELDS = [
        "id", "name", "muscle_groups", "joints_loaded", "movement_patterns",
        "equipment_required", "is_bilateral", "side", "priority_tier",
        "is_reps", "is_duration", "supports_weight",
        "estimated_rep_duration", "bilateral_pair_id",
    ]

    def test_all_hybrid_exercises_have_14_fields(self, hybrid_exercises):
        for ex in hybrid_exercises:
            for field in self._REQUIRED_FIELDS:
                assert hasattr(ex, field), (
                    f"Hybrid exercise '{ex.name}' missing field: {field}"
                )

    def test_hybrid_ids_are_unique(self, hybrid_exercises):
        ids = [ex.id for ex in hybrid_exercises]
        assert len(ids) == len(set(ids)), "Duplicate hybrid exercise ids found"

    def test_hybrid_names_are_non_empty(self, hybrid_exercises):
        for ex in hybrid_exercises:
            assert ex.name, f"Hybrid exercise with id={ex.id} has empty name"

    def test_hybrid_priority_tiers_valid(self, hybrid_exercises):
        for ex in hybrid_exercises:
            assert ex.priority_tier in {1, 2, 3}, (
                f"Hybrid exercise '{ex.name}' has invalid priority_tier: {ex.priority_tier}"
            )

    def test_hybrid_exercises_with_duration_flag(self, hybrid_exercises):
        """All hybrid timed exercises (no reps) must have is_duration=True."""
        for ex in hybrid_exercises:
            # If not rep-based (is_reps=False), must be duration-based
            if not ex.is_reps:
                assert ex.is_duration, (
                    f"Hybrid exercise '{ex.name}' has is_reps=False but is_duration=False"
                )


# ---------------------------------------------------------------------------
# 3. Movement annotations
# ---------------------------------------------------------------------------


class TestHybridMovementAnnotations:
    _LUMBAR_LOADING_IDS = {
        "hyb-004",  # SkiErg Sprint
        "hyb-006",  # Sandbag Lunge
        "hyb-007",  # Rowing Ergometer
        "hyb-009",  # Sandbag Clean and Press
        "hyb-011",  # Kettlebell Swing
        "hyb-014",  # Sandbag Over Shoulder
        "hyb-016",  # Dumbbell Suitcase Carry
        "hyb-019",  # Single-Arm KB Carry (Rack)
        "hyb-020",  # Tire Flip
    }

    _KNEE_LOADING_IDS = {
        "hyb-001",  # Sled Push
        "hyb-003",  # Wall Ball Shot
        "hyb-006",  # Sandbag Lunge
        "hyb-007",  # Rowing Ergometer
        "hyb-008",  # Burpee Broad Jump
        "hyb-010",  # Run
        "hyb-012",  # Box Jump
    }

    def test_lumbar_loading_exercises_annotated(self, hybrid_exercises):
        """Hybrid exercises known to load the lumbar spine have the annotation."""
        annotated = {
            ex.id for ex in hybrid_exercises
            if "lumbar_spine" in ex.joint_movements
        }
        for ex_id in self._LUMBAR_LOADING_IDS:
            assert ex_id in annotated, (
                f"Expected hybrid exercise {ex_id} to have lumbar_spine annotation"
            )

    def test_knee_loading_exercises_annotated(self, hybrid_exercises):
        """Hybrid exercises that load the knee have the annotation."""
        annotated = {
            ex.id for ex in hybrid_exercises
            if "knee" in ex.joint_movements
        }
        for ex_id in self._KNEE_LOADING_IDS:
            assert ex_id in annotated, (
                f"Expected hybrid exercise {ex_id} to have knee annotation"
            )

    def test_sled_push_knee_flexion_load(self, hybrid_exercises):
        sled_push = next(ex for ex in hybrid_exercises if ex.id == "hyb-001")
        movements = sled_push.joint_movements.get("knee", [])
        assert "load" in movements, "Sled Push should have knee:load annotation"
        assert "flexion" in movements, "Sled Push should have knee:flexion annotation"

    def test_skierg_sprint_lumbar_load(self, hybrid_exercises):
        skierg = next(ex for ex in hybrid_exercises if ex.id == "hyb-004")
        movements = skierg.joint_movements.get("lumbar_spine", [])
        assert "load" in movements, "SkiErg Sprint should have lumbar_spine:load annotation"


# ---------------------------------------------------------------------------
# 4. Safety filter still gates on hybrid exercises
# ---------------------------------------------------------------------------


def _make_injury(
    joint: str,
    region: str,
    pain_on: list[str],
    onset_days_ago: int = 30,
) -> Injury:
    """Helper to build a test Injury with a single InjuryState check-in."""
    # onset_days_ago=30 → remodeling phase (day 30 > 21)
    from datetime import timedelta
    ref_date = date(2026, 6, 6)
    onset = ref_date - timedelta(days=onset_days_ago)
    state = InjuryState(
        injury_id="test_inj",
        recorded_at=datetime(2026, 6, 6, 8, 0, 0, tzinfo=timezone.utc),
        inflammation="mild",
        pain_on=pain_on,  # type: ignore[arg-type]
        subjective_pain=3,
        load_tolerance_pct=0.7,
    )
    return Injury(
        id="test_inj",
        region=region,
        joint=joint,
        diagnosis=f"Test {joint} injury",
        snomed_code=None,
        onset_date=onset,
        current_phase=compute_phase(onset_days_ago),
        states=[state],
    )


class TestHybridSafetyFilter:
    ALL_EQUIPMENT = {
        "Sled", "Rower", "SkiErg", "Sandbag", "Dumbbell",
        "Medicine Ball", "Wall", "Kettlebell", "Box",
        "Assault Bike", "Rope", "Tire", "Yoga Mat",
        # base equipment too
        "Barbell", "Plate", "Rack", "Pull-Up Bar", "Miniband",
        "Resistance Band - Loop", "Resistance Band - With Handles",
    }

    def test_mico_lumbar_gates_skierg_sprint(self, exercises, kg):
        """Mico's lumbar injury (pain on flexion+load) should exclude SkiErg Sprint."""
        injury = _make_injury(
            joint="lumbar_spine",
            region="lumbar",
            pain_on=["flexion", "load"],
        )
        trace = conditional_safety_filter(
            candidates=exercises,
            injury=injury,
            available_equipment=self.ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )
        safe_ids = {ex.id for ex in trace.safe}
        assert "hyb-004" not in safe_ids, (
            "SkiErg Sprint should be excluded for lumbar injury with pain on flexion+load"
        )

    def test_mico_lumbar_gates_rowing_erg(self, exercises, kg):
        """Mico's lumbar injury (pain on load) should exclude Rowing Ergometer."""
        injury = _make_injury(
            joint="lumbar_spine",
            region="lumbar",
            pain_on=["load"],
        )
        trace = conditional_safety_filter(
            candidates=exercises,
            injury=injury,
            available_equipment=self.ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )
        safe_ids = {ex.id for ex in trace.safe}
        assert "hyb-007" not in safe_ids, (
            "Rowing Ergometer should be excluded for lumbar injury with pain on load"
        )

    def test_jordan_knee_gates_wall_ball(self, exercises, kg):
        """Jordan's knee injury (pain on flexion+load) should exclude Wall Ball Shot."""
        injury = _make_injury(
            joint="knee",
            region="knee",
            pain_on=["flexion", "load"],
        )
        trace = conditional_safety_filter(
            candidates=exercises,
            injury=injury,
            available_equipment=self.ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )
        safe_ids = {ex.id for ex in trace.safe}
        assert "hyb-003" not in safe_ids, (
            "Wall Ball Shot should be excluded for knee injury with pain on flexion+load"
        )

    def test_jordan_knee_gates_box_jump(self, exercises, kg):
        """Jordan's knee injury (pain on impact) should exclude Box Jump."""
        injury = _make_injury(
            joint="knee",
            region="knee",
            pain_on=["impact"],
        )
        trace = conditional_safety_filter(
            candidates=exercises,
            injury=injury,
            available_equipment=self.ALL_EQUIPMENT,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )
        safe_ids = {ex.id for ex in trace.safe}
        assert "hyb-012" not in safe_ids, (
            "Box Jump should be excluded for knee injury with pain on impact"
        )

    def test_no_injury_includes_all_hybrid_exercises(self, exercises, kg):
        """Without any injury, all hybrid exercises with available equipment are safe."""
        from app.graph.safety_filter import safety_filter

        all_equip = self.ALL_EQUIPMENT.copy()
        trace = safety_filter(
            candidates=exercises,
            injured_joints=[],
            available_equipment=all_equip,
            excluded_ids=set(),
            dislikes=set(),
            kg=kg,
        )
        safe_ids = {ex.id for ex in trace.safe}
        # Sled push should be safe when Sled is available and no injury
        assert "hyb-001" in safe_ids, (
            "Sled Push should be safe when no injury and Sled equipment available"
        )


# ---------------------------------------------------------------------------
# 5. Catalog hybrid equipment concepts
# ---------------------------------------------------------------------------


class TestHybridCatalogEquipment:
    def test_sled_in_catalog(self):
        catalog = build_concept_catalog()
        assert "sled" in catalog, "Expected 'sled' concept in catalog"
        sled = catalog["sled"]
        assert sled.type == "equipment"
        assert any("prowler" in lab.lower() for lab in sled.alt_labels)

    def test_rower_in_catalog(self):
        catalog = build_concept_catalog()
        assert "rower" in catalog, "Expected 'rower' concept in catalog"
        rower = catalog["rower"]
        assert rower.type == "equipment"
        assert any("concept2" in lab.lower() or "rowing" in lab.lower() for lab in rower.alt_labels)

    def test_assault_bike_in_catalog(self):
        catalog = build_concept_catalog()
        assert "assault_bike" in catalog
        bike = catalog["assault_bike"]
        assert bike.type == "equipment"

    def test_rope_in_catalog(self):
        catalog = build_concept_catalog()
        assert "rope" in catalog
        rope = catalog["rope"]
        assert rope.type == "equipment"

    def test_tire_in_catalog(self):
        catalog = build_concept_catalog()
        assert "tire" in catalog
        tire = catalog["tire"]
        assert tire.type == "equipment"

    def test_skierg_still_in_catalog(self):
        """SkiErg was already in the catalog as 'skier' — confirm it's still there."""
        catalog = build_concept_catalog()
        assert "skier" in catalog
        skierg = catalog["skier"]
        assert skierg.type == "equipment"
        assert any("skierg" in lab.lower() for lab in skierg.alt_labels)

    def test_equipment_count_increased(self):
        from app.ontology.catalog import count_by_type
        catalog = build_concept_catalog()
        counts = count_by_type(catalog)
        # Phase 11 added 5 items: sled, rower, assault_bike, rope, tire
        assert counts.get("equipment", 0) == 37, (
            f"Expected 37 equipment items (32 base + 5 hybrid), got {counts.get('equipment', 0)}"
        )
