"""
Phase 6 — Part 0 validation: Multi-member foundation.

Tests:
  1. list_members() returns both Jordan and Mico
  2. load_member_context("mbr_01HX9JORDAN") returns Jordan's full context
  3. load_member_context("mbr_MICO") returns Mico's full context with lumbar injury
  4. Mico's injury is in the lumbar spine region with correct SNOMED code
  5. Mico's hormone biomarker panel is present in labs
  6. GET /api/members returns both members (endpoint smoke test)
  7. GET /api/members/{member_id} returns full context for Jordan and Mico
  8. Backward-compatible: load_member_context() (no args) still returns Jordan
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.data.loader import list_members, load_member_context
from app.models.member import MemberContext, MemberSummary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def jordan() -> MemberContext:
    return load_member_context("mbr_01HX9JORDAN")


@pytest.fixture(scope="module")
def mico() -> MemberContext:
    return load_member_context("mbr_MICO")


@pytest.fixture(scope="module")
def summaries() -> list[MemberSummary]:
    return list_members()


# ---------------------------------------------------------------------------
# 1. list_members()
# ---------------------------------------------------------------------------


class TestListMembers:
    def test_returns_at_least_two_members(self, summaries):
        assert len(summaries) >= 2, (
            f"Expected at least 2 members, got {len(summaries)}: {[s.member_id for s in summaries]}"
        )

    def test_jordan_in_list(self, summaries):
        ids = {s.member_id for s in summaries}
        assert "mbr_01HX9JORDAN" in ids, f"Jordan not in member list: {ids}"

    def test_mico_in_list(self, summaries):
        ids = {s.member_id for s in summaries}
        assert "mbr_MICO" in ids, f"Mico not in member list: {ids}"

    def test_summaries_have_required_fields(self, summaries):
        for s in summaries:
            assert s.member_id, "MemberSummary missing member_id"
            assert s.name, "MemberSummary missing name"
            assert s.age > 0, "MemberSummary missing age"
            assert s.churn_risk_level, "MemberSummary missing churn_risk_level"
            assert s.adherence_trend, "MemberSummary missing adherence_trend"

    def test_jordan_churn_risk_elevated(self, summaries):
        jordan = next((s for s in summaries if s.member_id == "mbr_01HX9JORDAN"), None)
        assert jordan is not None
        assert jordan.churn_risk_level == "elevated"

    def test_mico_churn_risk_low(self, summaries):
        mico = next((s for s in summaries if s.member_id == "mbr_MICO"), None)
        assert mico is not None
        assert mico.churn_risk_level == "low"

    def test_mico_active_injury_is_lumbar(self, summaries):
        mico = next((s for s in summaries if s.member_id == "mbr_MICO"), None)
        assert mico is not None
        assert mico.active_injury is not None
        assert "lumbar" in mico.active_injury.lower(), (
            f"Expected Mico's active_injury to mention 'lumbar', got: {mico.active_injury}"
        )


# ---------------------------------------------------------------------------
# 2. Jordan full context
# ---------------------------------------------------------------------------


class TestJordanContext:
    def test_jordan_profile(self, jordan):
        assert jordan.profile.id == "mbr_01HX9JORDAN"
        assert jordan.profile.name == "Jordan Rivera"
        assert jordan.profile.age == 41

    def test_jordan_has_knee_injury(self, jordan):
        joints = [inj.joint for inj in jordan.injuries]
        assert "knee" in joints, f"Expected 'knee' injury for Jordan, got: {joints}"

    def test_jordan_has_11_sections(self, jordan):
        assert jordan.profile is not None
        assert len(jordan.goals) >= 1
        assert jordan.preferences is not None
        assert len(jordan.equipment_available) >= 1
        assert len(jordan.injuries) >= 1
        assert len(jordan.workout_history) >= 1
        assert jordan.adherence is not None
        assert jordan.biomarkers is not None
        assert jordan.labs is not None
        assert len(jordan.chat_history) >= 1
        assert jordan.coach_brief is not None

    def test_backward_compat_no_args(self):
        """load_member_context() without args still returns Jordan."""
        member = load_member_context()
        assert member.profile.id == "mbr_01HX9JORDAN"


# ---------------------------------------------------------------------------
# 3. Mico full context
# ---------------------------------------------------------------------------


class TestMicoContext:
    def test_mico_profile(self, mico):
        assert mico.profile.id == "mbr_MICO"
        assert mico.profile.name == "Mico"
        assert mico.profile.age == 35
        assert mico.profile.sex == "male"

    def test_mico_has_lumbar_injury(self, mico):
        assert len(mico.injuries) >= 1, "Mico should have at least one injury"
        joints = [inj.joint for inj in mico.injuries]
        assert "lumbar_spine" in joints, (
            f"Expected 'lumbar_spine' joint for Mico's injury, got: {joints}"
        )

    def test_mico_lumbar_injury_snomed_code(self, mico):
        lumbar = next((inj for inj in mico.injuries if inj.joint == "lumbar_spine"), None)
        assert lumbar is not None
        assert lumbar.snomed_code == "279039007", (
            f"Expected SNOMED 279039007 (low back pain), got: {lumbar.snomed_code}"
        )

    def test_mico_lumbar_injury_has_state_history(self, mico):
        lumbar = next((inj for inj in mico.injuries if inj.joint == "lumbar_spine"), None)
        assert lumbar is not None
        assert len(lumbar.states) >= 2, (
            f"Expected at least 2 injury states for Mico, got {len(lumbar.states)}"
        )

    def test_mico_lumbar_injury_state_has_flexion_pain(self, mico):
        """Mico's most recent state should have 'flexion' in pain_on."""
        lumbar = next((inj for inj in mico.injuries if inj.joint == "lumbar_spine"), None)
        assert lumbar is not None
        # States are stored as dicts; check the last one
        last_state = lumbar.states[-1]
        pain_on = last_state.get("pain_on", []) if isinstance(last_state, dict) else last_state.pain_on
        assert "flexion" in pain_on, (
            f"Expected 'flexion' in Mico's lumbar pain_on, got: {pain_on}"
        )

    def test_mico_has_11_sections(self, mico):
        assert mico.profile is not None
        assert len(mico.goals) >= 1
        assert mico.preferences is not None
        assert len(mico.equipment_available) >= 1
        assert len(mico.injuries) >= 1
        assert len(mico.workout_history) >= 1
        assert mico.adherence is not None
        assert mico.biomarkers is not None
        assert mico.labs is not None
        assert len(mico.chat_history) >= 1
        assert mico.coach_brief is not None

    def test_mico_adherence_stable(self, mico):
        assert mico.adherence.trend == "stable"

    def test_mico_good_adherence(self, mico):
        recent = mico.adherence.weekly_completion_pct[-1]
        assert recent.pct == 100

    def test_mico_hormone_panel(self, mico):
        """Mico's labs should include testosterone and cortisol."""
        assert mico.labs is not None
        assert mico.labs.blood_panel is not None
        panel = mico.labs.blood_panel
        assert panel.testosterone_ng_dl is not None, (
            "Expected testosterone_ng_dl in Mico's blood panel"
        )
        assert panel.cortisol_morning_mcg_dl is not None, (
            "Expected cortisol_morning_mcg_dl in Mico's blood panel"
        )
        assert panel.testosterone_ng_dl > 0
        assert panel.cortisol_morning_mcg_dl > 0

    def test_mico_trains_5x_per_week(self, mico):
        assert mico.preferences.training_days_per_week == 5

    def test_mico_has_full_gym_equipment(self, mico):
        equipment_set = {e.lower() for e in mico.equipment_available}
        assert "barbell" in equipment_set
        assert "pull-up bar" in equipment_set

    def test_mico_goals_include_hyrox(self, mico):
        goal_texts = [g.text.lower() for g in mico.goals]
        assert any("hyrox" in t for t in goal_texts), (
            f"Expected HYROX goal for Mico, got: {mico.goals}"
        )


# ---------------------------------------------------------------------------
# 4. Unknown member raises ValueError / 404
# ---------------------------------------------------------------------------


class TestUnknownMember:
    def test_load_unknown_member_raises(self):
        with pytest.raises(ValueError, match="not found"):
            load_member_context("mbr_DOES_NOT_EXIST")


# ---------------------------------------------------------------------------
# 5. API endpoint smoke tests
# ---------------------------------------------------------------------------


class TestMembersEndpoint:
    def test_list_members_endpoint(self, client):
        response = client.get("/api/members")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_list_members_returns_jordan(self, client):
        response = client.get("/api/members")
        data = response.json()
        ids = {m["member_id"] for m in data}
        assert "mbr_01HX9JORDAN" in ids

    def test_list_members_returns_mico(self, client):
        response = client.get("/api/members")
        data = response.json()
        ids = {m["member_id"] for m in data}
        assert "mbr_MICO" in ids

    def test_get_jordan_endpoint(self, client):
        response = client.get("/api/members/mbr_01HX9JORDAN")
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["id"] == "mbr_01HX9JORDAN"
        assert data["profile"]["name"] == "Jordan Rivera"

    def test_get_mico_endpoint(self, client):
        response = client.get("/api/members/mbr_MICO")
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["id"] == "mbr_MICO"
        assert data["profile"]["name"] == "Mico"

    def test_get_unknown_member_returns_404(self, client):
        response = client.get("/api/members/mbr_GHOST")
        assert response.status_code == 404

    def test_get_mico_has_lumbar_injury(self, client):
        response = client.get("/api/members/mbr_MICO")
        assert response.status_code == 200
        data = response.json()
        injuries = data.get("injuries", [])
        assert len(injuries) >= 1
        joints = [inj["joint"] for inj in injuries]
        assert "lumbar_spine" in joints, (
            f"Expected lumbar_spine injury in Mico's API response, got: {joints}"
        )
