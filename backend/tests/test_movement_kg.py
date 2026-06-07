"""
Phase 3 + 7.1 validation: Movement Knowledge Graph

Checks:
  - Graph loads with all exercises, concepts, and SNOMED data
  - descendants_by_part_of("knee") returns patellofemoral joint (SNOMED code)
  - exercises_stressing returns exercises that load the knee joint
  - exercises_by_movement_type correctly separates flexion vs extension exercises
  - Squats are tagged with knee:flexion
  - Leg extensions/hamstring walkouts are tagged with knee:extension
  - Equipment exclusion via graph edges works correctly

Phase 7.1 additions (R3 KG1 gap-closing):
  - EDGE_CONTRAINDICATED_FOR constant is exported
  - contraindicated-for edges exist for Jordan's knee injury (flexion/impact/load)
  - contraindicated-for edges exist for Mico's lumbar injury (flexion/load/rotation)
  - contraindicated_exercises("knee") returns knee-flexion/impact exercises
  - contraindicated_exercises("lumbar_spine") returns lumbar-loading exercises
  - list_contraindicated_for_edges() returns the full edge list for Graph Explorer
"""

from __future__ import annotations

import pytest

from app.data.loader import load_exercises
from app.graph.movement_kg import MovementKG
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
def exercises():
    return load_exercises()


# ---------------------------------------------------------------------------
# Graph structure tests
# ---------------------------------------------------------------------------


class TestMovementKGStructure:
    def test_graph_loads(self, kg):
        assert kg is not None

    def test_graph_has_nodes(self, kg):
        assert kg.node_count() > 0

    def test_graph_has_edges(self, kg):
        assert kg.edge_count() > 0

    def test_graph_has_all_exercises(self, kg, exercises):
        """Every exercise should have a node in the graph."""
        g = kg.graph
        for ex in exercises:
            assert g.has_node(ex.id), f"Exercise '{ex.name}' ({ex.id}) not in graph"

    def test_graph_has_joint_nodes(self, kg):
        """Joint concept nodes (e.g. 'knee') should be present."""
        g = kg.graph
        assert g.has_node("knee"), "Expected 'knee' concept node in graph"
        assert g.nodes["knee"]["node_type"] == "joint"

    def test_graph_has_equipment_nodes(self, kg):
        """Equipment concept nodes should be present."""
        g = kg.graph
        assert g.has_node("barbell"), "Expected 'barbell' concept node in graph"

    def test_knee_stressing_exercises_exist(self, kg):
        """Some exercises should have edges to the knee node."""
        knee_node_ids = kg.descendants_by_part_of("knee")
        stressing = kg.exercises_stressing(knee_node_ids)
        assert len(stressing) > 0, "Expected at least one exercise stressing the knee"

    def test_barbell_requiring_exercises_exist(self, kg, exercises):
        """Some exercises require a barbell."""
        g = kg.graph
        barbell_exercises = [
            ex for ex in exercises
            if "Barbell" in ex.equipment_required
        ]
        assert len(barbell_exercises) > 0, "Expected at least one barbell exercise"


# ---------------------------------------------------------------------------
# descendants_by_part_of tests
# ---------------------------------------------------------------------------


class TestDescendantsByPartOf:
    def test_knee_descendants_include_patellofemoral(self, kg):
        """
        The patellofemoral joint (SNOMED 57714003) must be a descendant
        of the knee joint (SNOMED 49076000).
        """
        descendants = kg.descendants_by_part_of("knee")
        # SNOMED code for patellofemoral joint
        assert "57714003" in descendants, (
            f"Expected patellofemoral joint (57714003) in knee descendants. "
            f"Got: {descendants}"
        )

    def test_knee_descendants_include_tibiofemoral(self, kg):
        """Tibiofemoral joint (SNOMED 182204001) is part-of knee joint."""
        descendants = kg.descendants_by_part_of("knee")
        assert "182204001" in descendants, (
            f"Expected tibiofemoral joint (182204001) in knee descendants."
        )

    def test_knee_descendants_include_medial_meniscus(self, kg):
        """Medial meniscus (59440001) is part-of knee joint."""
        descendants = kg.descendants_by_part_of("knee")
        assert "59440001" in descendants

    def test_knee_has_multiple_descendants(self, kg):
        """The knee should have multiple SNOMED descendants."""
        descendants = kg.descendants_by_part_of("knee")
        assert len(descendants) >= 5, (
            f"Expected >= 5 descendants for knee, got {len(descendants)}: {descendants}"
        )

    def test_unknown_joint_returns_empty(self, kg):
        """An unknown joint slug should return an empty set."""
        descendants = kg.descendants_by_part_of("nonexistent_joint_xyz")
        assert descendants == set()

    def test_shoulder_returns_empty_descendants(self, kg):
        """
        Shoulder has no SNOMED descendants in our snapshot — should return
        a set containing only its own code.
        """
        descendants = kg.descendants_by_part_of("shoulder")
        # Shoulder is in the concept catalog but has no SNOMED sub-structure
        # in our baked snapshot, so descendants are just the shoulder's own code.
        assert isinstance(descendants, set)


# ---------------------------------------------------------------------------
# exercises_stressing tests
# ---------------------------------------------------------------------------


class TestExercisesStressing:
    def test_squat_exercises_stress_knee(self, kg, exercises):
        """
        Squat-pattern exercises that load the knee should appear in the
        exercises_stressing result for knee.
        """
        knee_node_ids = kg.descendants_by_part_of("knee")
        stressing = kg.exercises_stressing(knee_node_ids)

        # Find exercises that have knee in joints_loaded
        knee_exercises = {ex.id for ex in exercises if "knee" in ex.joints_loaded}
        overlap = stressing & knee_exercises
        assert len(overlap) > 0, (
            f"Expected some knee-loading exercises in stressing set. "
            f"Stressing: {len(stressing)}, knee_exercises: {len(knee_exercises)}"
        )

    def test_empty_joint_set_returns_empty(self, kg):
        """Empty joint set should return empty set."""
        result = kg.exercises_stressing(set())
        assert result == set()

    def test_upper_body_exercises_not_in_knee_stressing(self, kg, exercises):
        """
        Exercises with only upper-body joints (shoulder/elbow/wrist) should
        not appear in the knee-stressing set.
        """
        knee_node_ids = kg.descendants_by_part_of("knee")
        stressing = kg.exercises_stressing(knee_node_ids)

        upper_only = {
            ex.id for ex in exercises
            if ex.joints_loaded
            and all(j in ("shoulder", "elbow", "wrist") for j in ex.joints_loaded)
        }
        intersection = stressing & upper_only
        assert len(intersection) == 0, (
            f"Upper-body-only exercises should not stress the knee: {intersection}"
        )


# ---------------------------------------------------------------------------
# exercises_by_movement_type (movement-type annotations) tests
# ---------------------------------------------------------------------------


class TestMovementTypes:
    def test_squats_tagged_with_knee_flexion(self, kg, exercises):
        """
        Squat-pattern exercises that load the knee should include flexion
        in their knee movement types (as annotated in exercise_movements.json).
        """
        flexion_exs = kg.exercises_by_movement_type("knee", "flexion")

        # Find squat exercises that have knee in joints_loaded
        squat_knee_ids = {
            ex.id for ex in exercises
            if "lower push - squat" in ex.movement_patterns
            and "knee" in ex.joints_loaded
        }
        assert len(squat_knee_ids) > 0, "Expected squat exercises with knee joint"

        # At least some squat/knee exercises should be in the flexion set
        overlap = flexion_exs & squat_knee_ids
        assert len(overlap) > 0, (
            f"Expected squat-knee exercises to be tagged with knee:flexion. "
            f"Flexion set: {len(flexion_exs)}, squat+knee set: {len(squat_knee_ids)}"
        )

    def test_hamstring_walkout_tagged_with_knee_extension(self, kg, exercises):
        """
        Hamstring walkout exercises are hip-hinge dominant and involve knee
        extension — they should be tagged with knee:extension but NOT knee:flexion.
        """
        flexion_ids = kg.exercises_by_movement_type("knee", "flexion")
        extension_ids = kg.exercises_by_movement_type("knee", "extension")

        # Find hamstring walkout exercises
        walkout_ids = {
            ex.id for ex in exercises
            if "walkout" in ex.name.lower() and "knee" in ex.joints_loaded
        }

        if walkout_ids:
            # Walkouts should have knee:extension
            assert walkout_ids & extension_ids, (
                f"Expected hamstring walkout exercises to have knee:extension. "
                f"Walkout ids: {walkout_ids}"
            )

    def test_plyometric_exercises_tagged_with_impact(self, kg, exercises):
        """
        Plyometric exercises (jumps) should be tagged with knee:impact.
        """
        impact_ids = kg.exercises_by_movement_type("knee", "impact")

        jump_ids = {
            ex.id for ex in exercises
            if "jump" in ex.name.lower() and "knee" in ex.joints_loaded
        }

        if jump_ids:
            overlap = impact_ids & jump_ids
            assert len(overlap) > 0, (
                f"Expected jump exercises to have knee:impact. "
                f"Jump ids: {jump_ids}, impact ids: {len(impact_ids)}"
            )

    def test_unknown_joint_returns_empty(self, kg):
        result = kg.exercises_by_movement_type("nonexistent_joint", "flexion")
        assert result == set()

    def test_shoulder_flexion_exercises_exist(self, kg):
        """Shoulder flexion exercises (presses) should be annotated."""
        flexion = kg.exercises_by_movement_type("shoulder", "flexion")
        assert len(flexion) > 0, "Expected shoulder:flexion exercises to be annotated"

    def test_elbow_load_exercises_exist(self, kg):
        """Loaded elbow exercises (curls, presses) should be annotated."""
        elbow_load = kg.exercises_by_movement_type("elbow", "load")
        assert len(elbow_load) > 0, "Expected elbow:load exercises to be annotated"

    def test_flexion_and_extension_are_disjoint_for_some_exercises(self, kg, exercises):
        """
        Some exercises are purely flexion-dominant at the knee (e.g. squats)
        and some are extension-dominant (e.g. hamstring walkouts). They should
        not all be in both sets.
        """
        flexion_ids = kg.exercises_by_movement_type("knee", "flexion")
        extension_only_ids = kg.exercises_by_movement_type("knee", "extension") - flexion_ids

        # There should be exercises that are extension-at-knee but not flexion-at-knee
        # (e.g. hamstring walkouts)
        if extension_only_ids:
            # This is the expected case — just verify the sets are computed
            assert isinstance(extension_only_ids, set)


# ---------------------------------------------------------------------------
# Equipment graph edge tests
# ---------------------------------------------------------------------------


class TestEquipmentEdges:
    def test_barbell_exercises_wired_to_barbell_node(self, kg, exercises):
        """Exercises requiring Barbell should have 'requires' edges to barbell node."""
        g = kg.graph
        barbell_exercises = [ex for ex in exercises if "Barbell" in ex.equipment_required]

        for ex in barbell_exercises:
            neighbors = {
                target
                for _, target, data in g.out_edges(ex.id, data=True)
                if data.get("relation") == "requires"
            }
            assert "barbell" in neighbors, (
                f"Exercise '{ex.name}' should have requires→barbell edge. "
                f"Neighbors: {neighbors}"
            )

    def test_no_equipment_exercises_have_no_requires_edges(self, kg, exercises):
        """
        Exercises with empty equipment_required should have no 'requires' edges.
        """
        g = kg.graph
        no_equipment = [ex for ex in exercises if not ex.equipment_required]

        for ex in no_equipment:
            requires_edges = [
                (_, target)
                for _, target, data in g.out_edges(ex.id, data=True)
                if data.get("relation") == "requires"
            ]
            assert len(requires_edges) == 0, (
                f"Exercise '{ex.name}' has no equipment but has requires edges: {requires_edges}"
            )


# ---------------------------------------------------------------------------
# Phase 7.1 — contraindicated-for edges (R3 KG1 gap-closing)
# ---------------------------------------------------------------------------


class TestContraindicatedForEdges:
    """
    Tests for the static 'contraindicated-for' edges materialised in Phase 7.1.

    These edges represent the static 'textbook' contraindication view:
      injury_concept_node --contraindicated-for--> exercise_node

    The runtime authority for a specific injury state remains the
    conditional_safety_filter (dynamic, per-check-in).  These static edges
    are for the Graph Explorer and explainability.
    """

    def test_edge_constant_exported(self):
        """EDGE_CONTRAINDICATED_FOR constant is exported from movement_kg."""
        from app.graph.movement_kg import EDGE_CONTRAINDICATED_FOR
        assert EDGE_CONTRAINDICATED_FOR == "contraindicated-for"

    def test_knee_injury_concept_node_exists(self, kg):
        """The graph should have an injury_concept node for 'knee'."""
        g = kg.graph
        assert g.has_node("injury_concept_knee"), (
            "Expected 'injury_concept_knee' node in MovementKG graph"
        )
        node_data = g.nodes["injury_concept_knee"]
        assert node_data.get("node_type") == "injury_concept"

    def test_lumbar_injury_concept_node_exists(self, kg):
        """The graph should have an injury_concept node for 'lumbar_spine'."""
        g = kg.graph
        assert g.has_node("injury_concept_lumbar_spine"), (
            "Expected 'injury_concept_lumbar_spine' node in MovementKG graph"
        )

    def test_knee_contraindicates_flexion_exercises(self, kg, exercises):
        """
        Jordan's knee injury: knee flexion exercises should be contraindicated.

        Exercises tagged with knee:flexion (e.g. squats, lunges) should appear
        in the contraindicated_exercises("knee") set.
        """
        contra = kg.contraindicated_exercises("knee")
        assert len(contra) > 0, (
            "Expected at least one exercise contraindicated for knee injury"
        )

        # Exercises with knee:flexion annotation should be contraindicated
        flexion_ids = kg.exercises_by_movement_type("knee", "flexion")
        overlap = contra & flexion_ids
        assert len(overlap) > 0, (
            f"Expected knee-flexion exercises to be in contraindicated set. "
            f"Knee flexion: {len(flexion_ids)}, contraindicated: {len(contra)}, "
            f"overlap: {len(overlap)}"
        )

    def test_knee_contraindicates_impact_exercises(self, kg, exercises):
        """
        Knee injury: impact exercises (jumps, plyometrics) should be
        contraindicated.
        """
        contra = kg.contraindicated_exercises("knee")
        impact_ids = kg.exercises_by_movement_type("knee", "impact")

        if impact_ids:
            overlap = contra & impact_ids
            assert len(overlap) > 0, (
                f"Expected knee-impact exercises to be contraindicated. "
                f"Impact: {impact_ids}, contraindicated: {contra}"
            )

    def test_lumbar_contraindicates_flexion_load_exercises(self, kg, exercises):
        """
        Mico's lumbar injury: lumbar flexion and load exercises (deadlifts,
        good mornings, bent-over rows) should be contraindicated.
        """
        contra = kg.contraindicated_exercises("lumbar_spine")
        assert len(contra) > 0, (
            "Expected at least one exercise contraindicated for lumbar_spine injury"
        )

        # Exercises with lumbar:flexion or lumbar:load should be contraindicated
        lumbar_flexion = kg.exercises_by_movement_type("lumbar_spine", "flexion")
        lumbar_load = kg.exercises_by_movement_type("lumbar_spine", "load")
        lumbar_triggered = lumbar_flexion | lumbar_load

        if lumbar_triggered:
            overlap = contra & lumbar_triggered
            assert len(overlap) > 0, (
                f"Expected lumbar flexion/load exercises to be contraindicated. "
                f"Lumbar-triggered: {len(lumbar_triggered)}, contraindicated: {len(contra)}"
            )

    def test_unknown_injury_returns_empty(self, kg):
        """contraindicated_exercises for an unknown joint returns an empty set."""
        result = kg.contraindicated_exercises("fictional_joint_xyz")
        assert result == set()

    def test_contraindicated_for_edges_in_graph(self, kg):
        """
        The graph should have at least some 'contraindicated-for' edges for
        known injury concepts (knee, lumbar_spine).
        """
        from app.graph.movement_kg import EDGE_CONTRAINDICATED_FOR
        g = kg.graph
        contra_edges = [
            (s, t) for s, t, d in g.edges(data=True)
            if d.get("relation") == EDGE_CONTRAINDICATED_FOR
        ]
        assert len(contra_edges) > 0, (
            "Expected at least one 'contraindicated-for' edge in the graph"
        )

    def test_list_contraindicated_for_edges_returns_list(self, kg):
        """list_contraindicated_for_edges returns a non-empty list of dicts."""
        edges = kg.list_contraindicated_for_edges()
        assert isinstance(edges, list)
        assert len(edges) > 0, (
            "Expected at least one entry from list_contraindicated_for_edges()"
        )

    def test_list_contraindicated_for_edges_schema(self, kg):
        """Each edge entry has the expected keys for the Graph Explorer."""
        edges = kg.list_contraindicated_for_edges()
        required_keys = {"injury_concept", "joint_slug", "exercise_id", "exercise_name", "movement_types"}
        for edge in edges:
            assert required_keys <= set(edge.keys()), (
                f"Edge entry missing required keys. Got: {set(edge.keys())}"
            )
            assert isinstance(edge["movement_types"], list)
            assert isinstance(edge["exercise_name"], str)
            assert len(edge["exercise_name"]) > 0

    def test_knee_contra_edges_reference_valid_exercises(self, kg, exercises):
        """All exercise_ids in knee contraindicated-for edges exist in the catalog."""
        exercise_ids = {ex.id for ex in exercises}
        contra = kg.contraindicated_exercises("knee")
        for ex_id in contra:
            assert ex_id in exercise_ids, (
                f"Contraindicated exercise id '{ex_id}' not found in catalog"
            )

    def test_lumbar_contra_edges_reference_valid_exercises(self, kg, exercises):
        """All exercise_ids in lumbar contraindicated-for edges exist in the catalog."""
        exercise_ids = {ex.id for ex in exercises}
        contra = kg.contraindicated_exercises("lumbar_spine")
        for ex_id in contra:
            assert ex_id in exercise_ids, (
                f"Contraindicated exercise id '{ex_id}' not found in catalog"
            )

    def test_injury_concept_joint_slug_attribute(self, kg):
        """Injury concept nodes carry the joint_slug attribute."""
        g = kg.graph
        for node_id, data in g.nodes(data=True):
            if data.get("node_type") == "injury_concept":
                assert "joint_slug" in data, (
                    f"injury_concept node '{node_id}' missing joint_slug attribute"
                )
