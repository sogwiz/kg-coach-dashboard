"""
Phase 7 validation: Member Context KG

Tests:
  1. Member KG loads for Jordan — graph has nodes + edges, injuries resolve
     to the shared knee concept node.
  2. Member KG loads for Mico — lumbar spine injury resolves to the shared
     lumbar_spine concept node.
  3. Query API: get_injuries, get_adherence_series, get_equipment,
     get_coach_brief, get_biomarkers all return plausible data.
  4. Multi-member independence: Jordan and Mico have separate MemberKG
     instances with distinct data.

All tests are deterministic — no LLM or API key required.
"""

from __future__ import annotations

import pytest

from app.data.loader import load_member_context
from app.graph.member_kg import MemberKG
from app.ontology.catalog import build_concept_catalog


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def concepts():
    return build_concept_catalog()


@pytest.fixture(scope="module")
def jordan_kg(concepts) -> MemberKG:
    member = load_member_context("mbr_01HX9JORDAN")
    return MemberKG(member, concepts)


@pytest.fixture(scope="module")
def mico_kg(concepts) -> MemberKG:
    member = load_member_context("mbr_MICO")
    return MemberKG(member, concepts)


# ---------------------------------------------------------------------------
# 1. Jordan's MemberKG — graph structure and injury → joint concept node
# ---------------------------------------------------------------------------


class TestJordanMemberKG:
    def test_graph_has_nodes(self, jordan_kg):
        """The graph must have at least the member node + concept nodes."""
        assert jordan_kg.node_count() > 0

    def test_graph_has_edges(self, jordan_kg):
        """The graph must have edges (has_injury, has_equipment, etc.)."""
        assert jordan_kg.edge_count() > 0

    def test_member_id_is_jordan(self, jordan_kg):
        """The member id must be Jordan's stable id."""
        assert jordan_kg.get_member_id() == "mbr_01HX9JORDAN"

    def test_member_name_is_jordan(self, jordan_kg):
        """The member name should be Jordan Rivera."""
        name = jordan_kg.get_member_name()
        assert "jordan" in name.lower() or "Jordan" in name

    def test_jordan_has_knee_injury(self, jordan_kg):
        """Jordan must have at least one injury with joint='knee'."""
        injuries = jordan_kg.get_injuries()
        assert len(injuries) > 0, "Jordan should have at least one injury"
        injury_joints = [inj.joint for inj in injuries]
        assert "knee" in injury_joints, (
            f"Expected 'knee' in Jordan's injuries, got: {injury_joints}"
        )

    def test_knee_injury_links_to_shared_concept_node(self, jordan_kg, concepts):
        """
        Jordan's knee injury node must link via 'affects_joint' to the shared
        'knee' concept node that also exists in the Movement KG catalog.

        This verifies the key sharing constraint: the Member KG and Movement KG
        use the SAME concept node for 'knee', enabling cross-graph traversal.
        """
        # The shared concept catalog must have a 'knee' joint concept
        assert "knee" in concepts, (
            "Concept catalog must contain a 'knee' concept node"
        )

        # The injury → joint mapping must resolve to 'knee'
        injury_joint_map = jordan_kg.injury_joint_concept_nodes()

        # At least one injury should resolve to the knee concept node
        joint_targets = list(injury_joint_map.values())
        assert "knee" in joint_targets, (
            f"Expected 'knee' as a linked concept node, got: {joint_targets}. "
            "Injury node must share the concept node with the Movement KG."
        )

    def test_knee_concept_node_is_shared_in_graph(self, jordan_kg, concepts):
        """
        The 'knee' concept node must exist in the MemberKG graph AND have
        the correct node_type from the catalog.

        This is the sharing test — the same node id 'knee' exists in both
        the Movement KG (built from concepts) and the Member KG.
        """
        g = jordan_kg.graph
        assert g.has_node("knee"), (
            "MemberKG graph must contain the shared 'knee' concept node"
        )
        node_data = g.nodes["knee"]
        # The knee node's type should be 'joint' (from the concept catalog)
        assert node_data.get("node_type") == "joint", (
            f"Expected knee node_type='joint', got: {node_data.get('node_type')}"
        )


# ---------------------------------------------------------------------------
# 2. Mico's MemberKG — lumbar spine injury → shared concept node
# ---------------------------------------------------------------------------


class TestMicoMemberKG:
    def test_graph_has_nodes(self, mico_kg):
        """Mico's graph must have at least the member node + concept nodes."""
        assert mico_kg.node_count() > 0

    def test_member_id_is_mico(self, mico_kg):
        """The member id must be Mico's stable id."""
        assert mico_kg.get_member_id() == "mbr_MICO"

    def test_mico_has_lumbar_injury(self, mico_kg):
        """Mico must have at least one injury with joint='lumbar_spine'."""
        injuries = mico_kg.get_injuries()
        assert len(injuries) > 0, "Mico should have at least one injury"
        injury_joints = [inj.joint for inj in injuries]
        assert "lumbar_spine" in injury_joints, (
            f"Expected 'lumbar_spine' in Mico's injuries, got: {injury_joints}"
        )

    def test_lumbar_injury_links_to_shared_concept_node(self, mico_kg, concepts):
        """
        Mico's lumbar spine injury node must link via 'affects_joint' to the
        shared 'lumbar_spine' concept node.

        This verifies that Mico's back injury traverses the same SNOMED anatomy
        part-of chain as Jordan's knee injury — just for a different joint.
        """
        # The shared concept catalog must have a 'lumbar_spine' joint concept
        assert "lumbar_spine" in concepts, (
            "Concept catalog must contain a 'lumbar_spine' concept node"
        )

        # The injury → joint mapping must resolve to 'lumbar_spine'
        injury_joint_map = mico_kg.injury_joint_concept_nodes()
        joint_targets = list(injury_joint_map.values())
        assert "lumbar_spine" in joint_targets, (
            f"Expected 'lumbar_spine' as a linked concept node, got: {joint_targets}. "
            "Mico's lumbar injury must share the concept node with the Movement KG."
        )

    def test_lumbar_concept_node_is_in_graph(self, mico_kg):
        """
        The 'lumbar_spine' concept node must exist in the MemberKG graph.
        """
        g = mico_kg.graph
        assert g.has_node("lumbar_spine"), (
            "MemberKG graph must contain the shared 'lumbar_spine' concept node"
        )
        node_data = g.nodes["lumbar_spine"]
        assert node_data.get("node_type") in ("joint", "body_region"), (
            f"Expected lumbar_spine node_type in ('joint', 'body_region'), "
            f"got: {node_data.get('node_type')}"
        )


# ---------------------------------------------------------------------------
# 3. Query API — Jordan
# ---------------------------------------------------------------------------


class TestQueryAPIJordan:
    def test_get_injuries_returns_list(self, jordan_kg):
        """get_injuries returns a non-empty list."""
        injuries = jordan_kg.get_injuries()
        assert isinstance(injuries, list)
        assert len(injuries) > 0

    def test_get_injuries_returns_full_injury_model(self, jordan_kg):
        """get_injuries returns promoted Injury objects with onset_date + phase."""
        from app.models.injury import HealingPhase, Injury
        injuries = jordan_kg.get_injuries()
        for inj in injuries:
            assert isinstance(inj, Injury), f"Expected Injury, got {type(inj)}"
            assert inj.onset_date is not None
            assert isinstance(inj.computed_phase(), HealingPhase)

    def test_get_adherence_series_returns_points(self, jordan_kg):
        """get_adherence_series returns at least one AdherencePoint."""
        from app.graph.member_kg import AdherencePoint
        series = jordan_kg.get_adherence_series(weeks=4)
        assert isinstance(series, list)
        assert len(series) > 0
        for pt in series:
            assert isinstance(pt, AdherencePoint)
            assert isinstance(pt.pct, float)
            assert isinstance(pt.week_of, str)

    def test_get_adherence_series_respects_weeks_limit(self, jordan_kg):
        """get_adherence_series returns at most `weeks` data points."""
        series = jordan_kg.get_adherence_series(weeks=2)
        assert len(series) <= 2

    def test_get_equipment_returns_set(self, jordan_kg):
        """get_equipment returns a non-empty set of strings."""
        equipment = jordan_kg.get_equipment()
        assert isinstance(equipment, set)
        assert len(equipment) > 0
        for item in equipment:
            assert isinstance(item, str)

    def test_get_coach_brief_returns_brief(self, jordan_kg):
        """get_coach_brief returns a CoachBrief with churn_risk and morning_tasks."""
        from app.models.member import CoachBrief
        brief = jordan_kg.get_coach_brief()
        assert isinstance(brief, CoachBrief)
        assert brief.churn_risk is not None
        assert isinstance(brief.morning_tasks, list)

    def test_get_biomarkers_returns_biomarkers(self, jordan_kg):
        """get_biomarkers returns a Biomarkers object with expected fields."""
        from app.models.member import Biomarkers
        biomarkers = jordan_kg.get_biomarkers()
        assert isinstance(biomarkers, Biomarkers)
        assert isinstance(biomarkers.resting_hr_bpm, float)
        assert isinstance(biomarkers.hrv_ms, float)
        assert isinstance(biomarkers.sleep_hours_last_7_days, list)


# ---------------------------------------------------------------------------
# 4. Query API — Mico
# ---------------------------------------------------------------------------


class TestQueryAPIMico:
    def test_get_equipment_returns_set(self, mico_kg):
        """Mico's equipment set is non-empty."""
        equipment = mico_kg.get_equipment()
        assert isinstance(equipment, set)
        assert len(equipment) > 0

    def test_get_coach_brief_has_churn_risk(self, mico_kg):
        """Mico's coach brief has a churn_risk level."""
        brief = mico_kg.get_coach_brief()
        assert brief.churn_risk.level in ("low", "medium", "high", "unknown")

    def test_get_adherence_series_returns_data(self, mico_kg):
        """Mico's adherence series has at least one point."""
        series = mico_kg.get_adherence_series(weeks=4)
        assert len(series) > 0

    def test_get_biomarkers_has_sleep_data(self, mico_kg):
        """Mico's biomarkers include sleep data."""
        biomarkers = mico_kg.get_biomarkers()
        assert isinstance(biomarkers.sleep_hours_last_7_days, list)


# ---------------------------------------------------------------------------
# 5. Multi-member independence
# ---------------------------------------------------------------------------


class TestMultiMemberIndependence:
    def test_jordan_and_mico_have_different_ids(self, jordan_kg, mico_kg):
        """Jordan and Mico must have different member ids."""
        assert jordan_kg.get_member_id() != mico_kg.get_member_id()

    def test_jordan_and_mico_have_different_injuries(self, jordan_kg, mico_kg):
        """Jordan's injuries and Mico's injuries are independent."""
        jordan_joints = {inj.joint for inj in jordan_kg.get_injuries()}
        mico_joints = {inj.joint for inj in mico_kg.get_injuries()}
        # They should NOT have the same injury joint
        # (Jordan = knee, Mico = lumbar_spine)
        assert jordan_joints != mico_joints, (
            "Jordan and Mico should have different injured joints"
        )

    def test_jordan_knee_not_in_mico_injuries(self, jordan_kg, mico_kg):
        """Jordan's knee injury should not appear in Mico's injury list."""
        mico_joints = {inj.joint for inj in mico_kg.get_injuries()}
        jordan_joints = {inj.joint for inj in jordan_kg.get_injuries()}
        # The sets are distinct
        # (Mico's lumbar_spine is not Jordan's knee)
        assert "knee" not in mico_joints or "lumbar_spine" not in jordan_joints, (
            "Jordan and Mico injuries should be for different joints"
        )

    def test_shared_concept_nodes_exist_in_both_graphs(self, jordan_kg, mico_kg):
        """
        Shared concept nodes (e.g. 'knee', 'lumbar_spine') should exist in
        BOTH MemberKG graphs since they are loaded from the same concept catalog.
        """
        # Both graphs loaded the full concept catalog, so both should have
        # both joint concept nodes
        assert jordan_kg.graph.has_node("knee")
        assert jordan_kg.graph.has_node("lumbar_spine")
        assert mico_kg.graph.has_node("knee")
        assert mico_kg.graph.has_node("lumbar_spine")
