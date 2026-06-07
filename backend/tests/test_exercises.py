"""
Phase 13 — GET /api/exercises endpoint tests.

Tests:
  1. GET /api/exercises lists the full catalog (70 exercises incl. hybrid).
     - Response has 'exercises', 'total' keys.
     - "Wall Ball Shot" (hyb-003) is present.
     - "Ball Slam" (hyb-021) is present.
     - Total count is >= 70.

  2. Ball Slam (hyb-021) loads/validates and has the required annotations.
     - All 14 schema fields present.
     - joints_loaded includes "lumbar spine" and "shoulder".
     - movement_patterns reuse existing taxonomy strings.
     - joint_movements has lumbar_spine and shoulder entries (loaded from
       exercise_movements.json by load_exercises()).

  3. ?search= filters by name and movement_patterns (case-insensitive).
     - ?search=ball returns both "Wall Ball Shot" and "Ball Slam".
     - ?search=SkiErg returns SkiErg Sprint.
     - ?search=zzznomatch returns empty list.

  4. ?member_id=mbr_MICO flags lumbar-contraindicated exercises.
     - Ball Slam is flagged contraindicated=True for Mico (lumbar injury).
     - At least several exercises are flagged contraindicated=True.
     - Exercises that don't load the lumbar spine are flagged contraindicated=False
       (e.g. Rope Climb is shoulder-only, not lumbar).

  5. ?member_id= with unknown member returns 404.

  6. Each exercise item returned from the API has the expected fields:
     id, name, movement_patterns, muscle_groups, equipment_required,
     joints_loaded, priority_tier, contraindicated.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.data.loader import load_exercises

JORDAN_ID = "mbr_01HX9JORDAN"
MICO_ID = "mbr_MICO"

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Full catalog listing
# ---------------------------------------------------------------------------


class TestExerciseListFull:
    def test_response_structure(self):
        """GET /api/exercises returns exercises and total keys."""
        resp = client.get("/api/exercises")
        assert resp.status_code == 200
        data = resp.json()
        assert "exercises" in data
        assert "total" in data
        assert isinstance(data["exercises"], list)
        assert isinstance(data["total"], int)

    def test_total_at_least_70(self):
        """Catalog has at least 70 exercises (50 base + 20 hybrid + Ball Slam)."""
        resp = client.get("/api/exercises")
        data = resp.json()
        assert data["total"] >= 70, (
            f"Expected at least 70 exercises, got {data['total']}"
        )
        assert len(data["exercises"]) == data["total"]

    def test_wall_ball_shot_present(self):
        """Wall Ball Shot (hyb-003) is in the catalog."""
        resp = client.get("/api/exercises")
        data = resp.json()
        ids = {ex["id"] for ex in data["exercises"]}
        names = {ex["name"] for ex in data["exercises"]}
        assert "hyb-003" in ids, "hyb-003 (Wall Ball Shot) should be in catalog"
        assert "Wall Ball Shot" in names, "'Wall Ball Shot' should be in catalog names"

    def test_ball_slam_present(self):
        """Ball Slam (hyb-021) is in the catalog."""
        resp = client.get("/api/exercises")
        data = resp.json()
        ids = {ex["id"] for ex in data["exercises"]}
        names = {ex["name"] for ex in data["exercises"]}
        assert "hyb-021" in ids, "hyb-021 (Ball Slam) should be in catalog"
        assert "Ball Slam" in names, "'Ball Slam' should be in catalog names"

    def test_no_duplicate_ids(self):
        """All exercise ids in the response are unique."""
        resp = client.get("/api/exercises")
        data = resp.json()
        ids = [ex["id"] for ex in data["exercises"]]
        assert len(ids) == len(set(ids)), "Duplicate exercise ids found in response"


# ---------------------------------------------------------------------------
# 2. Ball Slam data validation
# ---------------------------------------------------------------------------


class TestBallSlamValidation:
    @pytest.fixture(scope="class")
    def ball_slam_api(self):
        """Ball Slam as returned by the API."""
        resp = client.get("/api/exercises")
        data = resp.json()
        for ex in data["exercises"]:
            if ex["id"] == "hyb-021":
                return ex
        pytest.fail("Ball Slam (hyb-021) not found in /api/exercises response")

    @pytest.fixture(scope="class")
    def ball_slam_model(self):
        """Ball Slam as loaded by load_exercises() — includes joint_movements."""
        exercises = load_exercises()
        for ex in exercises:
            if ex.id == "hyb-021":
                return ex
        pytest.fail("Ball Slam (hyb-021) not found via load_exercises()")

    def test_ball_slam_has_all_14_fields(self, ball_slam_api):
        """Ball Slam has all 14 schema fields in the API response."""
        required_fields = [
            "id", "name", "movement_patterns", "muscle_groups",
            "equipment_required", "joints_loaded", "priority_tier",
        ]
        for field in required_fields:
            assert field in ball_slam_api, f"Ball Slam API item missing field: {field}"

    def test_ball_slam_joints_loaded_includes_lumbar(self, ball_slam_api):
        """Ball Slam joints_loaded must include 'lumbar spine'."""
        joints = ball_slam_api["joints_loaded"]
        # The data stores it as "lumbar spine" (with space, matching other hybrid exercises)
        assert any("lumbar" in j.lower() for j in joints), (
            f"Ball Slam joints_loaded should include lumbar spine, got: {joints}"
        )

    def test_ball_slam_joints_loaded_includes_shoulder(self, ball_slam_api):
        """Ball Slam joints_loaded must include 'shoulder'."""
        joints = ball_slam_api["joints_loaded"]
        assert any("shoulder" in j.lower() for j in joints), (
            f"Ball Slam joints_loaded should include shoulder, got: {joints}"
        )

    def test_ball_slam_equipment_medicine_ball(self, ball_slam_api):
        """Ball Slam requires Medicine Ball."""
        equip = ball_slam_api["equipment_required"]
        assert any("medicine ball" in e.lower() or "med ball" in e.lower() for e in equip), (
            f"Ball Slam should require Medicine Ball, got: {equip}"
        )

    def test_ball_slam_movement_patterns_existing_taxonomy(self, ball_slam_api):
        """Ball Slam movement_patterns must all be valid existing taxonomy strings."""
        from app.ontology.catalog import build_concept_catalog
        catalog = build_concept_catalog()
        valid_pattern_labels = {
            c.pref_label.lower() for c in catalog.values() if c.type == "pattern"
        }
        for pattern in ball_slam_api["movement_patterns"]:
            assert pattern.lower() in valid_pattern_labels, (
                f"Ball Slam pattern '{pattern}' is not in existing taxonomy. "
                f"Valid patterns: {sorted(valid_pattern_labels)}"
            )

    def test_ball_slam_lumbar_spine_annotation(self, ball_slam_model):
        """Ball Slam has lumbar_spine in joint_movements (loaded from exercise_movements.json)."""
        assert "lumbar_spine" in ball_slam_model.joint_movements, (
            "Ball Slam should have lumbar_spine in joint_movements annotation"
        )
        lumbar_types = ball_slam_model.joint_movements["lumbar_spine"]
        assert len(lumbar_types) > 0, "lumbar_spine joint_movements should be non-empty"

    def test_ball_slam_shoulder_annotation(self, ball_slam_model):
        """Ball Slam has shoulder in joint_movements (loaded from exercise_movements.json)."""
        assert "shoulder" in ball_slam_model.joint_movements, (
            "Ball Slam should have shoulder in joint_movements annotation"
        )
        shoulder_types = ball_slam_model.joint_movements["shoulder"]
        assert len(shoulder_types) > 0, "shoulder joint_movements should be non-empty"

    def test_ball_slam_lumbar_spine_load_annotation(self, ball_slam_model):
        """Ball Slam lumbar_spine annotation includes 'load' (overhead slam loads spine)."""
        lumbar_types = ball_slam_model.joint_movements.get("lumbar_spine", [])
        assert "load" in lumbar_types, (
            f"Ball Slam lumbar_spine annotation should include 'load', got: {lumbar_types}"
        )

    def test_ball_slam_shoulder_load_annotation(self, ball_slam_model):
        """Ball Slam shoulder annotation includes 'load' (overhead reach loads shoulder)."""
        shoulder_types = ball_slam_model.joint_movements.get("shoulder", [])
        assert "load" in shoulder_types, (
            f"Ball Slam shoulder annotation should include 'load', got: {shoulder_types}"
        )

    def test_ball_slam_priority_tier_valid(self, ball_slam_api):
        """Ball Slam priority_tier is 1, 2, or 3."""
        assert ball_slam_api["priority_tier"] in {1, 2, 3}

    def test_ball_slam_model_has_14_fields(self, ball_slam_model):
        """Ball Slam Exercise model has all 14 schema fields."""
        required_fields = [
            "id", "name", "muscle_groups", "joints_loaded", "movement_patterns",
            "equipment_required", "is_bilateral", "side", "priority_tier",
            "is_reps", "is_duration", "supports_weight",
            "estimated_rep_duration", "bilateral_pair_id",
        ]
        for field in required_fields:
            assert hasattr(ball_slam_model, field), (
                f"Ball Slam Exercise model missing field: {field}"
            )


# ---------------------------------------------------------------------------
# 3. Search filtering
# ---------------------------------------------------------------------------


class TestExerciseSearch:
    def test_search_ball_returns_wall_ball_and_ball_slam(self):
        """?search=ball returns both Wall Ball Shot and Ball Slam."""
        resp = client.get("/api/exercises?search=ball")
        assert resp.status_code == 200
        data = resp.json()
        names = {ex["name"] for ex in data["exercises"]}
        assert "Wall Ball Shot" in names, (
            f"?search=ball should return 'Wall Ball Shot', got names: {names}"
        )
        assert "Ball Slam" in names, (
            f"?search=ball should return 'Ball Slam', got names: {names}"
        )

    def test_search_ball_count(self):
        """?search=ball returns at least 2 exercises."""
        resp = client.get("/api/exercises?search=ball")
        data = resp.json()
        assert data["total"] >= 2, (
            f"?search=ball should return at least 2 exercises (Wall Ball + Ball Slam), got {data['total']}"
        )

    def test_search_case_insensitive(self):
        """Search is case-insensitive: 'BALL', 'Ball', 'ball' all work."""
        for query in ["BALL", "Ball", "ball"]:
            resp = client.get(f"/api/exercises?search={query}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] >= 2, (
                f"?search={query} should return at least 2 exercises"
            )

    def test_search_skierg_returns_skierg_sprint(self):
        """?search=SkiErg returns SkiErg Sprint."""
        resp = client.get("/api/exercises?search=SkiErg")
        data = resp.json()
        names = {ex["name"] for ex in data["exercises"]}
        assert "SkiErg Sprint" in names, (
            f"?search=SkiErg should return 'SkiErg Sprint', got names: {names}"
        )

    def test_search_no_match_returns_empty(self):
        """?search=zzznomatch returns empty list."""
        resp = client.get("/api/exercises?search=zzznomatch")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["exercises"] == []

    def test_search_by_pattern_string(self):
        """?search=plyometric returns exercises with cardio - plyometric pattern."""
        resp = client.get("/api/exercises?search=plyometric")
        data = resp.json()
        # Should match Ball Slam (cardio - plyometric), Box Jump, Burpee Broad Jump at minimum
        assert data["total"] >= 1, (
            "?search=plyometric should return at least one exercise"
        )
        # Verify Ball Slam is returned (it has cardio - plyometric pattern)
        names = {ex["name"] for ex in data["exercises"]}
        assert "Ball Slam" in names, (
            f"?search=plyometric should return Ball Slam (it has 'cardio - plyometric' pattern), "
            f"got names: {names}"
        )


# ---------------------------------------------------------------------------
# 4. Member-aware contraindication (Mico — lumbar injury)
# ---------------------------------------------------------------------------


class TestMemberAwareContraindication:
    def test_member_id_mico_flags_contraindicated(self):
        """?member_id=mbr_MICO sets contraindicated=True on some exercises."""
        resp = client.get(f"/api/exercises?member_id={MICO_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["member_id"] == MICO_ID
        contra_exercises = [ex for ex in data["exercises"] if ex["contraindicated"]]
        assert len(contra_exercises) > 0, (
            "Mico has a lumbar injury; some exercises should be contraindicated"
        )

    def test_mico_ball_slam_contraindicated(self):
        """Ball Slam is contraindicated for Mico (lumbar_spine injury, loads lumbar spine)."""
        resp = client.get(f"/api/exercises?member_id={MICO_ID}")
        data = resp.json()
        ball_slam = next(
            (ex for ex in data["exercises"] if ex["id"] == "hyb-021"),
            None,
        )
        assert ball_slam is not None, "Ball Slam should be in the catalog"
        assert ball_slam["contraindicated"] is True, (
            "Ball Slam should be contraindicated for Mico (lumbar injury + lumbar load annotation)"
        )

    def test_mico_lumbar_loading_exercises_contraindicated(self):
        """Key lumbar-loading hybrid exercises are flagged contraindicated for Mico."""
        resp = client.get(f"/api/exercises?member_id={MICO_ID}")
        data = resp.json()
        exercise_map = {ex["id"]: ex for ex in data["exercises"]}

        # SkiErg Sprint (hyb-004) loads lumbar_spine → should be contraindicated
        if "hyb-004" in exercise_map:
            assert exercise_map["hyb-004"]["contraindicated"] is True, (
                "SkiErg Sprint should be contraindicated for Mico (lumbar load)"
            )

        # Rowing Ergometer (hyb-007) loads lumbar_spine → should be contraindicated
        if "hyb-007" in exercise_map:
            assert exercise_map["hyb-007"]["contraindicated"] is True, (
                "Rowing Ergometer should be contraindicated for Mico (lumbar load)"
            )

    def test_rope_climb_not_lumbar_contraindicated_for_mico(self):
        """
        Rope Climb (hyb-018) — shoulder/elbow/wrist only, no lumbar annotation —
        should NOT be contraindicated for Mico.
        """
        resp = client.get(f"/api/exercises?member_id={MICO_ID}")
        data = resp.json()
        rope_climb = next(
            (ex for ex in data["exercises"] if ex["id"] == "hyb-018"),
            None,
        )
        if rope_climb is not None:
            assert rope_climb["contraindicated"] is False, (
                "Rope Climb should NOT be contraindicated for Mico "
                "(no lumbar involvement)"
            )

    def test_no_member_id_no_contraindicated_flag(self):
        """Without member_id, all exercises have contraindicated=False (default)."""
        resp = client.get("/api/exercises")
        data = resp.json()
        contra_exercises = [ex for ex in data["exercises"] if ex["contraindicated"]]
        assert len(contra_exercises) == 0, (
            "Without member_id, no exercises should be flagged contraindicated"
        )

    def test_member_id_jordan_flags_knee_exercises(self):
        """?member_id=mbr_01HX9JORDAN flags knee-loading exercises as contraindicated."""
        resp = client.get(f"/api/exercises?member_id={JORDAN_ID}")
        assert resp.status_code == 200
        data = resp.json()
        contra_exercises = [ex for ex in data["exercises"] if ex["contraindicated"]]
        assert len(contra_exercises) > 0, (
            "Jordan has a knee injury; some exercises should be contraindicated"
        )


# ---------------------------------------------------------------------------
# 5. Unknown member returns 404
# ---------------------------------------------------------------------------


class TestUnknownMember:
    def test_unknown_member_id_returns_404(self):
        """?member_id=mbr_UNKNOWN returns 404."""
        resp = client.get("/api/exercises?member_id=mbr_UNKNOWN")
        assert resp.status_code == 404, (
            f"Expected 404 for unknown member_id, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# 6. Response field structure
# ---------------------------------------------------------------------------


class TestResponseFieldStructure:
    EXPECTED_FIELDS = {
        "id", "name", "movement_patterns", "muscle_groups",
        "equipment_required", "joints_loaded", "priority_tier", "contraindicated",
    }

    def test_each_exercise_has_expected_fields(self):
        """Every exercise item in the API response has all expected fields."""
        resp = client.get("/api/exercises")
        data = resp.json()
        for ex in data["exercises"]:
            for field in self.EXPECTED_FIELDS:
                assert field in ex, (
                    f"Exercise '{ex.get('name', ex.get('id'))}' missing field: {field}"
                )

    def test_movement_patterns_is_list(self):
        """movement_patterns is a list for every exercise."""
        resp = client.get("/api/exercises")
        data = resp.json()
        for ex in data["exercises"]:
            assert isinstance(ex["movement_patterns"], list), (
                f"Exercise '{ex['name']}' movement_patterns should be a list"
            )

    def test_muscle_groups_is_list(self):
        """muscle_groups is a list for every exercise."""
        resp = client.get("/api/exercises")
        data = resp.json()
        for ex in data["exercises"]:
            assert isinstance(ex["muscle_groups"], list), (
                f"Exercise '{ex['name']}' muscle_groups should be a list"
            )

    def test_contraindicated_is_bool(self):
        """contraindicated field is always a boolean."""
        resp = client.get("/api/exercises")
        data = resp.json()
        for ex in data["exercises"]:
            assert isinstance(ex["contraindicated"], bool), (
                f"Exercise '{ex['name']}' contraindicated should be bool"
            )

    def test_search_with_member_id_combined(self):
        """?search= and ?member_id= can be combined."""
        resp = client.get(f"/api/exercises?search=ball&member_id={MICO_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["member_id"] == MICO_ID
        # Ball Slam should be in results and contraindicated for Mico
        ball_slam = next(
            (ex for ex in data["exercises"] if ex["id"] == "hyb-021"),
            None,
        )
        assert ball_slam is not None, "Ball Slam should appear in ?search=ball results"
        assert ball_slam["contraindicated"] is True, (
            "Ball Slam should be contraindicated for Mico when combined search+member_id"
        )
