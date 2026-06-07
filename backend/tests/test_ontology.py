"""
Phase 2 validation: concept catalog counts and SNOMED anatomy graph.

Checks:
  - Catalog has exactly 19 muscles, 9 joints, 36 patterns, 32 equipment
  - SNOMED snapshot loads with valid part-of edges
  - Knee region → knee joint → patellofemoral joint hierarchy exists
  - Descendant traversal from knee region finds patellofemoral joint
"""

from __future__ import annotations

import pytest

from app.ontology.catalog import build_concept_catalog, count_by_type
from app.ontology.loader import get_descendants_by_part_of, load_snomed_anatomy


# ---------------------------------------------------------------------------
# Concept catalog tests
# ---------------------------------------------------------------------------


class TestConceptCatalog:
    def setup_method(self):
        self.catalog = build_concept_catalog()

    def test_catalog_is_non_empty(self):
        assert len(self.catalog) > 0

    def test_muscle_count(self):
        counts = count_by_type(self.catalog)
        assert counts.get("muscle", 0) == 19, (
            f"Expected 19 muscles, got {counts.get('muscle', 0)}"
        )

    def test_joint_count(self):
        counts = count_by_type(self.catalog)
        assert counts.get("joint", 0) == 9, (
            f"Expected 9 joints, got {counts.get('joint', 0)}"
        )

    def test_pattern_count(self):
        counts = count_by_type(self.catalog)
        assert counts.get("pattern", 0) == 36, (
            f"Expected 36 patterns, got {counts.get('pattern', 0)}"
        )

    def test_equipment_count(self):
        counts = count_by_type(self.catalog)
        assert counts.get("equipment", 0) == 32, (
            f"Expected 32 equipment items, got {counts.get('equipment', 0)}"
        )

    def test_knee_joint_exists(self):
        assert "knee" in self.catalog, "Expected 'knee' concept in catalog"
        knee = self.catalog["knee"]
        assert knee.type == "joint"
        assert knee.snomed_code == "49076000"

    def test_quadriceps_muscle_exists(self):
        assert "quads" in self.catalog
        quads = self.catalog["quads"]
        assert quads.type == "muscle"
        assert "quadriceps" in quads.alt_labels

    def test_squat_pattern_exists(self):
        assert "lower_push_squat" in self.catalog
        squat = self.catalog["lower_push_squat"]
        assert squat.type == "pattern"
        # alt_labels should include common synonyms
        assert any("squat" in label.lower() for label in squat.alt_labels)

    def test_barbell_equipment_exists(self):
        assert "barbell" in self.catalog
        barbell = self.catalog["barbell"]
        assert barbell.type == "equipment"

    def test_all_concepts_have_pref_label(self):
        for concept_id, concept in self.catalog.items():
            assert concept.pref_label, f"Concept '{concept_id}' missing pref_label"

    def test_all_concepts_have_valid_type(self):
        valid_types = {"joint", "muscle", "pattern", "equipment", "injury", "body_region"}
        for concept_id, concept in self.catalog.items():
            assert concept.type in valid_types, (
                f"Concept '{concept_id}' has invalid type: {concept.type}"
            )

    def test_concept_ids_are_unique(self):
        # dict keying already enforces this, but verify no overwrites
        all_ids = list(self.catalog.keys())
        assert len(all_ids) == len(set(all_ids))

    def test_snomed_joints_have_codes(self):
        """All joint concepts should have a SNOMED code."""
        joints = {k: v for k, v in self.catalog.items() if v.type == "joint"}
        for concept_id, concept in joints.items():
            assert concept.snomed_code is not None, (
                f"Joint '{concept_id}' missing snomed_code"
            )

    def test_hip_adductors_slug_matches_exercises_json(self):
        """
        exercises.json uses 'hip adductors' — the catalog should have a concept
        that covers this via pref_label or alt_labels.
        """
        # The catalog uses 'hip_adductors' as the slug
        assert "hip_adductors" in self.catalog
        concept = self.catalog["hip_adductors"]
        assert "adductors" in concept.alt_labels or "hip adductor" in concept.alt_labels


# ---------------------------------------------------------------------------
# SNOMED anatomy tests
# ---------------------------------------------------------------------------


class TestSnomedAnatomy:
    def setup_method(self):
        self.snomed = load_snomed_anatomy()

    def test_snomed_loads_non_empty(self):
        assert len(self.snomed) > 0

    def test_snomed_has_at_least_10_concepts(self):
        assert len(self.snomed) >= 10, (
            f"Expected >= 10 SNOMED concepts, got {len(self.snomed)}"
        )

    def test_knee_region_concept_exists(self):
        """SNOMED 72696002 = Knee region structure."""
        assert "72696002" in self.snomed
        knee_region = self.snomed["72696002"]
        assert knee_region.type == "body_region"

    def test_knee_joint_concept_exists(self):
        """SNOMED 49076000 = Knee joint structure."""
        assert "49076000" in self.snomed
        knee_joint = self.snomed["49076000"]
        assert knee_joint.type == "joint"

    def test_patellofemoral_joint_concept_exists(self):
        """SNOMED 57714003 = Patellofemoral joint structure."""
        assert "57714003" in self.snomed
        pf_joint = self.snomed["57714003"]
        assert pf_joint.type == "joint"

    def test_knee_joint_part_of_knee_region(self):
        """Knee joint (49076000) must be part-of knee region (72696002)."""
        knee_joint = self.snomed["49076000"]
        assert "72696002" in knee_joint.part_of, (
            f"Expected knee joint part_of to include knee region '72696002', "
            f"got: {knee_joint.part_of}"
        )

    def test_patellofemoral_part_of_knee_joint(self):
        """Patellofemoral joint (57714003) must be part-of knee joint (49076000)."""
        pf_joint = self.snomed["57714003"]
        assert "49076000" in pf_joint.part_of, (
            f"Expected PF joint part_of to include knee joint '49076000', "
            f"got: {pf_joint.part_of}"
        )

    def test_medial_meniscus_part_of_knee_joint(self):
        """Medial meniscus (59440001) must be part-of knee joint (49076000)."""
        assert "59440001" in self.snomed
        medial_meniscus = self.snomed["59440001"]
        assert "49076000" in medial_meniscus.part_of

    def test_lateral_meniscus_part_of_knee_joint(self):
        """Lateral meniscus (64927001) must be part-of knee joint (49076000)."""
        assert "64927001" in self.snomed
        lateral_meniscus = self.snomed["64927001"]
        assert "49076000" in lateral_meniscus.part_of

    def test_injury_concepts_loaded(self):
        """PFPS injury concept should be indexed."""
        assert "57773001" in self.snomed, "PFPS (57773001) not in SNOMED index"

    def test_all_concepts_have_pref_label(self):
        for code, concept in self.snomed.items():
            assert concept.pref_label, f"SNOMED concept {code} missing pref_label"


# ---------------------------------------------------------------------------
# Descendant traversal tests
# ---------------------------------------------------------------------------


class TestPartOfTraversal:
    def setup_method(self):
        self.snomed = load_snomed_anatomy()

    def test_knee_region_descendants_include_knee_joint(self):
        """Descendants of knee region must include the knee joint."""
        descendants = get_descendants_by_part_of(self.snomed, "72696002")
        assert "49076000" in descendants, (
            f"Expected knee joint (49076000) in descendants of knee region. "
            f"Got: {descendants}"
        )

    def test_knee_region_descendants_include_patellofemoral(self):
        """Descendants of knee region must include the patellofemoral joint."""
        descendants = get_descendants_by_part_of(self.snomed, "72696002")
        assert "57714003" in descendants, (
            f"Expected patellofemoral joint (57714003) in descendants of knee region. "
            f"Got: {descendants}"
        )

    def test_knee_joint_descendants_include_patellofemoral(self):
        """
        Patellofemoral joint is part-of knee joint, so it should appear
        as a descendant of the knee joint node directly.
        """
        descendants = get_descendants_by_part_of(self.snomed, "49076000")
        assert "57714003" in descendants, (
            f"Expected patellofemoral joint (57714003) in descendants of knee joint. "
            f"Got: {descendants}"
        )

    def test_knee_region_has_multiple_descendants(self):
        """The knee region should have at least 5 descendants."""
        descendants = get_descendants_by_part_of(self.snomed, "72696002")
        assert len(descendants) >= 5, (
            f"Expected >= 5 descendants of knee region, got {len(descendants)}: {descendants}"
        )

    def test_isolated_concept_has_no_descendants(self):
        """A concept with no children should return an empty set."""
        # Patellofemoral joint has no children in our snapshot
        pf_descendants = get_descendants_by_part_of(self.snomed, "57714003")
        assert len(pf_descendants) == 0, (
            f"Expected 0 descendants for PF joint, got: {pf_descendants}"
        )


# ---------------------------------------------------------------------------
# Lumbar spine subtree tests (Phase 6)
# ---------------------------------------------------------------------------


class TestLumbarAnatomy:
    def setup_method(self):
        self.snomed = load_snomed_anatomy()

    def test_lumbar_spine_concept_exists(self):
        """SNOMED 122496007 = Lumbar spine structure."""
        assert "122496007" in self.snomed, (
            "Lumbar spine concept (122496007) not found in SNOMED index"
        )
        lumbar = self.snomed["122496007"]
        assert lumbar.type == "body_region"

    def test_lumbar_intervertebral_joint_exists(self):
        """SNOMED 297179000 = Lumbar intervertebral joint."""
        assert "297179000" in self.snomed, (
            "Lumbar intervertebral joint (297179000) not found in SNOMED index"
        )
        joint = self.snomed["297179000"]
        assert joint.type == "joint"

    def test_lumbar_intervertebral_joint_part_of_lumbar_spine(self):
        """Lumbar intervertebral joint (297179000) must be part-of lumbar spine (122496007)."""
        joint = self.snomed["297179000"]
        assert "122496007" in joint.part_of, (
            f"Expected lumbar joint part_of to include lumbar spine '122496007', "
            f"got: {joint.part_of}"
        )

    def test_lumbar_injury_concept_loaded(self):
        """Low back pain concept (279039007) should be indexed."""
        assert "279039007" in self.snomed, (
            "Low back pain (279039007) not found in SNOMED index"
        )
        lbp = self.snomed["279039007"]
        assert lbp.type == "injury"

    def test_lumbar_disc_part_of_lumbar_spine(self):
        """Lumbar intervertebral disc (244944005) must be part-of lumbar spine."""
        assert "244944005" in self.snomed
        disc = self.snomed["244944005"]
        assert "122496007" in disc.part_of

    def test_erector_spinae_part_of_lumbar_spine(self):
        """Erector spinae (46467000) must be part-of lumbar spine."""
        assert "46467000" in self.snomed
        erector = self.snomed["46467000"]
        assert "122496007" in erector.part_of


class TestLumbarPartOfTraversal:
    def setup_method(self):
        self.snomed = load_snomed_anatomy()

    def test_lumbar_spine_descendants_non_empty(self):
        """descendants_by_part_of('lumbar_spine') code returns non-empty set."""
        descendants = get_descendants_by_part_of(self.snomed, "122496007")
        assert len(descendants) > 0, (
            "Expected non-empty descendants for lumbar spine (122496007)"
        )

    def test_lumbar_spine_descendants_include_intervertebral_joint(self):
        """Lumbar intervertebral joint must appear as descendant of lumbar spine."""
        descendants = get_descendants_by_part_of(self.snomed, "122496007")
        assert "297179000" in descendants, (
            f"Expected lumbar intervertebral joint (297179000) in lumbar descendants. "
            f"Got: {descendants}"
        )

    def test_lumbar_spine_descendants_include_erector_spinae(self):
        """Erector spinae must appear as descendant of lumbar spine."""
        descendants = get_descendants_by_part_of(self.snomed, "122496007")
        assert "46467000" in descendants, (
            f"Expected erector spinae (46467000) in lumbar descendants. "
            f"Got: {descendants}"
        )

    def test_lumbar_spine_has_multiple_descendants(self):
        """The lumbar spine should have at least 3 descendants."""
        descendants = get_descendants_by_part_of(self.snomed, "122496007")
        assert len(descendants) >= 3, (
            f"Expected >= 3 descendants of lumbar spine, got {len(descendants)}: {descendants}"
        )

    def test_kg_lumbar_spine_descendants_via_catalog(self):
        """
        MovementKG.descendants_by_part_of('lumbar_spine') returns non-empty set,
        meaning exercises stressing lumbar_spine can be correctly filtered.
        """
        from app.data.loader import load_exercises
        from app.graph.movement_kg import MovementKG
        from app.ontology.catalog import build_concept_catalog

        exercises = load_exercises()
        concepts = build_concept_catalog()
        kg = MovementKG(exercises, concepts, self.snomed)

        lumbar_descendants = kg.descendants_by_part_of("lumbar_spine")
        assert len(lumbar_descendants) > 0, (
            "Expected non-empty lumbar descendants from MovementKG"
        )
        assert "lumbar_spine" in lumbar_descendants, (
            "Expected 'lumbar_spine' slug itself in descendants set"
        )

    def test_kg_lumbar_spine_exercises_stressing(self):
        """
        At least one exercise in the catalog stresses the lumbar_spine
        (e.g. Walking Toe Touches, Cow Pose, SkiErg, Hamstring Walkout).
        """
        from app.data.loader import load_exercises
        from app.graph.movement_kg import MovementKG
        from app.ontology.catalog import build_concept_catalog

        exercises = load_exercises()
        concepts = build_concept_catalog()
        kg = MovementKG(exercises, concepts, self.snomed)

        lumbar_nodes = kg.descendants_by_part_of("lumbar_spine")
        stressing = kg.exercises_stressing(lumbar_nodes)
        assert len(stressing) > 0, (
            "Expected at least one exercise stressing lumbar_spine, got none"
        )

    def test_knee_subtree_still_intact(self):
        """Adding lumbar subtree must not break the knee subtree."""
        descendants = get_descendants_by_part_of(self.snomed, "72696002")
        assert "49076000" in descendants, (
            "Knee joint (49076000) missing from knee region descendants after lumbar extension"
        )
        assert "57714003" in descendants, (
            "Patellofemoral joint (57714003) missing from knee region descendants after lumbar extension"
        )
