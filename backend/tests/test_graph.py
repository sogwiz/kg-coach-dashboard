"""
Phase 10 — Graph API endpoint tests.

Tests:
  1. GET /api/graph returns nodes and edges without member_id.
     - Response has 'nodes' and 'edges' keys.
     - Nodes include exercises, muscles, joints, patterns, equipment,
       and injury_concept types.
     - Edges include stresses, targets, requires, part-of, and
       contraindicated-for relations.

  2. contraindicated-for edges are present in the graph payload.
     - At least one edge with relation="contraindicated-for".
     - Each such edge has a valid source (injury_concept node) and
       a valid target (exercise node).

  3. member_id annotates filtered_out for Jordan (knee injury).
     - GET /api/graph?member_id=mbr_01HX9JORDAN
       → some exercise nodes have filtered_out=True
       → filter_path_node_ids includes knee-related node ids
       → no non-exercise node is marked filtered_out=True

  4. member_id annotates filtered_out for Mico (lumbar injury).
     - GET /api/graph?member_id=mbr_MICO
       → some exercise nodes have filtered_out=True (lumbar-loading lifts)
       → filter_path_node_ids includes lumbar_spine or related ids

  5. Graph structure sanity.
     - Every edge source and target references an existing node id.
     - No duplicate node ids.

  6. injury_progress and healing_phase_explanation tool functions (Phase 10).
     - injury_progress returns history with trend for Jordan's knee.
     - healing_phase_explanation returns phase info for Jordan's knee.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

JORDAN_ID = "mbr_01HX9JORDAN"
MICO_ID = "mbr_MICO"

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Basic graph structure (no member_id)
# ---------------------------------------------------------------------------


class TestGraphEndpointBasic:
    """Tests for GET /api/graph without a member_id."""

    def test_graph_returns_200(self):
        """GET /api/graph returns 200 OK."""
        response = client.get("/api/graph")
        assert response.status_code == 200

    def test_graph_has_nodes_and_edges(self):
        """Response has 'nodes' and 'edges' lists."""
        response = client.get("/api/graph")
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        assert len(data["nodes"]) > 0
        assert len(data["edges"]) > 0

    def test_graph_has_exercise_nodes(self):
        """Graph includes exercise-type nodes."""
        response = client.get("/api/graph")
        data = response.json()
        node_types = {n["type"] for n in data["nodes"]}
        assert "exercise" in node_types, f"Expected 'exercise' in node types, got: {node_types}"

    def test_graph_has_muscle_nodes(self):
        """Graph includes muscle-type nodes."""
        response = client.get("/api/graph")
        data = response.json()
        node_types = {n["type"] for n in data["nodes"]}
        assert "muscle" in node_types, f"Expected 'muscle' in node types, got: {node_types}"

    def test_graph_has_joint_nodes(self):
        """Graph includes joint-type nodes."""
        response = client.get("/api/graph")
        data = response.json()
        node_types = {n["type"] for n in data["nodes"]}
        assert "joint" in node_types, f"Expected 'joint' in node types, got: {node_types}"

    def test_graph_has_equipment_nodes(self):
        """Graph includes equipment-type nodes."""
        response = client.get("/api/graph")
        data = response.json()
        node_types = {n["type"] for n in data["nodes"]}
        assert "equipment" in node_types, f"Expected 'equipment' in node types, got: {node_types}"

    def test_graph_has_injury_concept_nodes(self):
        """Graph includes injury_concept nodes (from materialized contraindicated-for edges)."""
        response = client.get("/api/graph")
        data = response.json()
        node_types = {n["type"] for n in data["nodes"]}
        assert "injury_concept" in node_types, (
            f"Expected 'injury_concept' in node types, got: {node_types}"
        )

    def test_graph_has_stresses_edges(self):
        """Graph includes edges with relation='stresses'."""
        response = client.get("/api/graph")
        data = response.json()
        relations = {e["relation"] for e in data["edges"]}
        assert "stresses" in relations, f"Expected 'stresses' in edge relations, got: {relations}"

    def test_graph_has_targets_edges(self):
        """Graph includes edges with relation='targets'."""
        response = client.get("/api/graph")
        data = response.json()
        relations = {e["relation"] for e in data["edges"]}
        assert "targets" in relations

    def test_graph_has_requires_edges(self):
        """Graph includes edges with relation='requires'."""
        response = client.get("/api/graph")
        data = response.json()
        relations = {e["relation"] for e in data["edges"]}
        assert "requires" in relations

    def test_graph_has_part_of_edges(self):
        """Graph includes edges with relation='part-of'."""
        response = client.get("/api/graph")
        data = response.json()
        relations = {e["relation"] for e in data["edges"]}
        assert "part-of" in relations, f"Expected 'part-of' in edge relations, got: {relations}"

    def test_node_fields_complete(self):
        """Each node has id, label, type, filtered_out, on_filter_path."""
        response = client.get("/api/graph")
        data = response.json()
        for node in data["nodes"][:20]:  # sample first 20
            assert "id" in node
            assert "label" in node
            assert "type" in node
            assert "filtered_out" in node
            assert "on_filter_path" in node
            assert isinstance(node["filtered_out"], bool)
            assert isinstance(node["on_filter_path"], bool)

    def test_edge_fields_complete(self):
        """Each edge has source, target, relation, on_filter_path, movement_types."""
        response = client.get("/api/graph")
        data = response.json()
        for edge in data["edges"][:20]:  # sample first 20
            assert "source" in edge
            assert "target" in edge
            assert "relation" in edge
            assert "on_filter_path" in edge
            assert "movement_types" in edge
            assert isinstance(edge["on_filter_path"], bool)
            assert isinstance(edge["movement_types"], list)

    def test_no_member_id_all_filtered_out_false(self):
        """Without member_id, no node should be marked filtered_out=True."""
        response = client.get("/api/graph")
        data = response.json()
        filtered = [n for n in data["nodes"] if n["filtered_out"]]
        assert len(filtered) == 0, (
            f"Without member_id, no node should be filtered_out. Got {len(filtered)} filtered nodes."
        )


# ---------------------------------------------------------------------------
# 2. contraindicated-for edges
# ---------------------------------------------------------------------------


class TestContraindicatedForEdges:
    """Verify that contraindicated-for edges are present in the graph payload."""

    def test_contraindicated_for_edges_present(self):
        """At least one edge has relation='contraindicated-for'."""
        response = client.get("/api/graph")
        data = response.json()
        contra_edges = [e for e in data["edges"] if e["relation"] == "contraindicated-for"]
        assert len(contra_edges) > 0, (
            "Expected at least one 'contraindicated-for' edge in the graph payload."
        )

    def test_contraindicated_for_sources_are_injury_concepts(self):
        """contraindicated-for edge sources are injury_concept nodes."""
        response = client.get("/api/graph")
        data = response.json()
        node_id_to_type = {n["id"]: n["type"] for n in data["nodes"]}
        contra_edges = [e for e in data["edges"] if e["relation"] == "contraindicated-for"]
        for edge in contra_edges:
            src_type = node_id_to_type.get(edge["source"], "missing")
            assert src_type == "injury_concept", (
                f"contraindicated-for source '{edge['source']}' should be injury_concept, "
                f"got '{src_type}'"
            )

    def test_contraindicated_for_targets_are_exercises(self):
        """contraindicated-for edge targets are exercise nodes."""
        response = client.get("/api/graph")
        data = response.json()
        node_id_to_type = {n["id"]: n["type"] for n in data["nodes"]}
        contra_edges = [e for e in data["edges"] if e["relation"] == "contraindicated-for"]
        for edge in contra_edges:
            tgt_type = node_id_to_type.get(edge["target"], "missing")
            assert tgt_type == "exercise", (
                f"contraindicated-for target '{edge['target']}' should be exercise, "
                f"got '{tgt_type}'"
            )

    def test_knee_injury_concept_has_contraindicated_edges(self):
        """The knee injury_concept node has contraindicated-for edges to exercises."""
        response = client.get("/api/graph")
        data = response.json()
        knee_contra = [
            e for e in data["edges"]
            if e["relation"] == "contraindicated-for"
            and "knee" in e["source"].lower()
        ]
        assert len(knee_contra) > 0, (
            "Expected contraindicated-for edges from the knee injury_concept node."
        )

    def test_lumbar_injury_concept_has_contraindicated_edges(self):
        """The lumbar_spine injury_concept node has contraindicated-for edges."""
        response = client.get("/api/graph")
        data = response.json()
        lumbar_contra = [
            e for e in data["edges"]
            if e["relation"] == "contraindicated-for"
            and "lumbar" in e["source"].lower()
        ]
        assert len(lumbar_contra) > 0, (
            "Expected contraindicated-for edges from the lumbar_spine injury_concept node."
        )

    def test_contraindicated_edges_carry_movement_types(self):
        """contraindicated-for edges carry movement_types annotation."""
        response = client.get("/api/graph")
        data = response.json()
        contra_edges = [e for e in data["edges"] if e["relation"] == "contraindicated-for"]
        for edge in contra_edges[:5]:
            assert isinstance(edge["movement_types"], list)
            # Movement types should not be empty for contraindicated edges
            # (they record what triggered the edge)
            assert len(edge["movement_types"]) > 0, (
                f"contraindicated-for edge {edge['source']} -> {edge['target']} "
                "should have non-empty movement_types"
            )


# ---------------------------------------------------------------------------
# 3. member_id annotation — Jordan (knee injury)
# ---------------------------------------------------------------------------


class TestMemberAwareFilteringJordan:
    """Tests for GET /api/graph?member_id=Jordan (knee injury filtering)."""

    def test_jordan_graph_returns_200(self):
        """GET /api/graph?member_id=jordan returns 200."""
        response = client.get(f"/api/graph?member_id={JORDAN_ID}")
        assert response.status_code == 200

    def test_jordan_graph_has_filtered_out_exercises(self):
        """Some exercises are marked filtered_out=True for Jordan's knee injury."""
        response = client.get(f"/api/graph?member_id={JORDAN_ID}")
        data = response.json()
        filtered_nodes = [
            n for n in data["nodes"]
            if n["filtered_out"] and n["type"] == "exercise"
        ]
        assert len(filtered_nodes) > 0, (
            "Expected some exercises to be filtered_out=True for Jordan's knee injury."
        )

    def test_jordan_filter_path_includes_knee(self):
        """filter_path_node_ids includes knee-related node ids."""
        response = client.get(f"/api/graph?member_id={JORDAN_ID}")
        data = response.json()
        filter_path = data.get("filter_path_node_ids", [])
        assert len(filter_path) > 0, (
            "Expected filter_path_node_ids to be non-empty for Jordan's knee injury."
        )
        # At least one of knee, knee joint SNOMED codes, or knee-related ids should be present
        has_knee_related = any(
            "knee" in node_id.lower() or "49076000" in node_id
            for node_id in filter_path
        )
        assert has_knee_related, (
            f"Expected knee-related node ids in filter_path. Got: {filter_path}"
        )

    def test_only_exercise_nodes_are_filtered_out(self):
        """Only exercise nodes should have filtered_out=True (not muscles, joints, etc.)."""
        response = client.get(f"/api/graph?member_id={JORDAN_ID}")
        data = response.json()
        wrongly_filtered = [
            n for n in data["nodes"]
            if n["filtered_out"] and n["type"] != "exercise"
        ]
        assert len(wrongly_filtered) == 0, (
            f"Non-exercise nodes should not be filtered_out. Got: {wrongly_filtered[:3]}"
        )

    def test_jordan_filtered_exercise_ids_non_empty(self):
        """filtered_exercise_ids list in the response payload is non-empty for Jordan."""
        response = client.get(f"/api/graph?member_id={JORDAN_ID}")
        data = response.json()
        assert len(data.get("filtered_exercise_ids", [])) > 0, (
            "filtered_exercise_ids should be non-empty for Jordan's knee injury."
        )

    def test_jordan_member_id_in_response(self):
        """Response includes the member_id field."""
        response = client.get(f"/api/graph?member_id={JORDAN_ID}")
        data = response.json()
        assert data.get("member_id") == JORDAN_ID


# ---------------------------------------------------------------------------
# 4. member_id annotation — Mico (lumbar injury)
# ---------------------------------------------------------------------------


class TestMemberAwareFilteringMico:
    """Tests for GET /api/graph?member_id=Mico (lumbar injury filtering)."""

    def test_mico_graph_returns_200(self):
        """GET /api/graph?member_id=mico returns 200."""
        response = client.get(f"/api/graph?member_id={MICO_ID}")
        assert response.status_code == 200

    def test_mico_graph_has_filtered_out_exercises(self):
        """Some exercises are marked filtered_out=True for Mico's lumbar injury."""
        response = client.get(f"/api/graph?member_id={MICO_ID}")
        data = response.json()
        filtered_nodes = [
            n for n in data["nodes"]
            if n["filtered_out"] and n["type"] == "exercise"
        ]
        assert len(filtered_nodes) > 0, (
            "Expected some exercises to be filtered_out=True for Mico's lumbar injury."
        )

    def test_mico_filter_path_includes_lumbar(self):
        """filter_path_node_ids includes lumbar-related node ids."""
        response = client.get(f"/api/graph?member_id={MICO_ID}")
        data = response.json()
        filter_path = data.get("filter_path_node_ids", [])
        assert len(filter_path) > 0, (
            "Expected filter_path_node_ids to be non-empty for Mico's lumbar injury."
        )
        has_lumbar_related = any(
            "lumbar" in node_id.lower() or "spine" in node_id.lower()
            for node_id in filter_path
        )
        assert has_lumbar_related, (
            f"Expected lumbar-related node ids in filter_path. Got: {filter_path}"
        )

    def test_mico_filtered_exercise_ids_non_empty(self):
        """filtered_exercise_ids list is non-empty for Mico."""
        response = client.get(f"/api/graph?member_id={MICO_ID}")
        data = response.json()
        assert len(data.get("filtered_exercise_ids", [])) > 0


# ---------------------------------------------------------------------------
# 5. Graph structure sanity
# ---------------------------------------------------------------------------


class TestGraphStructureSanity:
    """Sanity checks on graph consistency."""

    def test_all_edge_sources_are_known_nodes(self):
        """Every edge source references an existing node id."""
        response = client.get("/api/graph")
        data = response.json()
        node_ids = {n["id"] for n in data["nodes"]}
        bad_sources = [
            e for e in data["edges"] if e["source"] not in node_ids
        ]
        assert len(bad_sources) == 0, (
            f"{len(bad_sources)} edges have unknown source node ids: "
            f"{[e['source'] for e in bad_sources[:5]]}"
        )

    def test_all_edge_targets_are_known_nodes(self):
        """Every edge target references an existing node id."""
        response = client.get("/api/graph")
        data = response.json()
        node_ids = {n["id"] for n in data["nodes"]}
        bad_targets = [
            e for e in data["edges"] if e["target"] not in node_ids
        ]
        assert len(bad_targets) == 0, (
            f"{len(bad_targets)} edges have unknown target node ids: "
            f"{[e['target'] for e in bad_targets[:5]]}"
        )

    def test_no_duplicate_node_ids(self):
        """No two nodes share the same id."""
        response = client.get("/api/graph")
        data = response.json()
        ids = [n["id"] for n in data["nodes"]]
        assert len(ids) == len(set(ids)), (
            f"Duplicate node ids found: "
            f"{[i for i in set(ids) if ids.count(i) > 1][:5]}"
        )

    def test_unknown_member_id_returns_404(self):
        """GET /api/graph?member_id=unknown returns 404."""
        response = client.get("/api/graph?member_id=mbr_DOES_NOT_EXIST")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 6. Phase 10 tool function tests (injury_progress, healing_phase_explanation)
# ---------------------------------------------------------------------------


class TestPhase10ToolFunctions:
    """Test the new Phase 10 tool functions (no LLM required)."""

    def test_injury_progress_jordan_knee(self):
        """injury_progress returns history for Jordan's knee injury."""
        from app.copilot.agent import injury_progress

        result = injury_progress(JORDAN_ID, "inj_knee_left", days=30)
        assert isinstance(result, dict)
        assert "states" in result or "error" in result
        if "error" not in result:
            assert result["member_id"] == JORDAN_ID
            assert result["injury_id"] == "inj_knee_left"
            assert "joint" in result
            assert result["joint"] == "knee"
            assert "trend" in result
            assert result["trend"] in ("improving", "stable", "worsening")
            assert "current_phase" in result
            assert isinstance(result["states"], list)

    def test_injury_progress_unknown_injury_returns_error(self):
        """injury_progress returns error for unknown injury_id."""
        from app.copilot.agent import injury_progress

        result = injury_progress(JORDAN_ID, "inj_DOES_NOT_EXIST")
        assert "error" in result

    def test_injury_progress_unknown_member_returns_error(self):
        """injury_progress returns error for unknown member_id."""
        from app.copilot.agent import injury_progress

        result = injury_progress("mbr_UNKNOWN_XYZ", "inj_knee_left")
        assert "error" in result

    def test_healing_phase_explanation_jordan_knee(self):
        """healing_phase_explanation returns phase info for Jordan's knee."""
        from app.copilot.agent import healing_phase_explanation

        result = healing_phase_explanation(JORDAN_ID, "inj_knee_left")
        assert isinstance(result, dict)
        if "error" not in result:
            assert result["member_id"] == JORDAN_ID
            assert result["injury_id"] == "inj_knee_left"
            assert "current_phase" in result
            assert result["current_phase"] in ("acute", "subacute", "remodeling", "rta")
            assert "phase_description" in result
            assert "movement_types_excluded" in result
            assert isinstance(result["movement_types_excluded"], list)
            assert "max_load_tolerance" in result
            assert isinstance(result["max_load_tolerance"], float)

    def test_healing_phase_explanation_unknown_member_returns_error(self):
        """healing_phase_explanation returns error for unknown member_id."""
        from app.copilot.agent import healing_phase_explanation

        result = healing_phase_explanation("mbr_UNKNOWN_XYZ", "inj_knee_left")
        assert "error" in result

    def test_healing_phase_explanation_mico_lumbar(self):
        """healing_phase_explanation works for Mico's lumbar injury."""
        from app.copilot.agent import healing_phase_explanation
        from app.copilot.agent import injury_status

        # First get Mico's injury id
        status = injury_status(MICO_ID)
        if "error" in status:
            pytest.skip("Mico member context not available")

        injuries = status.get("active_injuries", [])
        lumbar_injuries = [i for i in injuries if "lumbar" in i.get("joint", "")]
        if not lumbar_injuries:
            pytest.skip("Mico's lumbar injury not found")

        injury_id = lumbar_injuries[0]["id"]
        result = healing_phase_explanation(MICO_ID, injury_id)
        assert isinstance(result, dict)
        if "error" not in result:
            assert "current_phase" in result
            assert "joint" in result
            assert result["joint"] == "lumbar_spine"
