"""
Phase 5 validation: Dynamic Injury Model

Tests cover:
  1. HealingPhase auto-computation from days since onset
  2. Phase override by coach takes precedence over computed phase
  3. InjuryState validation (bounds on pain scale and load tolerance)
  4. Injury.current_state() returns most recent state
  5. Injury.state_for_date() returns correct historical state
  6. Injury.has_checkin_today() logic
  7. Injury.days_since_onset() with reference dates
  8. Jordan Rivera's injury from member-context.json loads and validates
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.data.loader import load_member_context
from app.models.healing import compute_phase
from app.models.injury import HealingPhase, Injury, InjuryState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_injury(
    onset_date: date,
    states: list[InjuryState] | None = None,
    phase_override: HealingPhase | None = None,
) -> Injury:
    return Injury(
        id="test_inj",
        region="left knee",
        joint="knee",
        diagnosis="Test injury",
        snomed_code=None,
        onset_date=onset_date,
        current_phase=HealingPhase.ACUTE,  # will be recomputed
        phase_override=phase_override,
        states=states or [],
    )


def _make_state(
    injury_id: str,
    recorded_at: datetime,
    pain_on: list | None = None,
    subjective_pain: int = 3,
    load_tolerance_pct: float = 0.6,
    inflammation: str = "mild",
) -> InjuryState:
    return InjuryState(
        injury_id=injury_id,
        recorded_at=recorded_at,
        inflammation=inflammation,  # type: ignore[arg-type]
        pain_on=pain_on or [],
        subjective_pain=subjective_pain,
        load_tolerance_pct=load_tolerance_pct,
    )


# ---------------------------------------------------------------------------
# Phase computation from days since onset
# ---------------------------------------------------------------------------


class TestHealingPhaseComputation:
    """Verify compute_phase() maps day ranges to the correct phase."""

    @pytest.mark.parametrize("days, expected_phase", [
        (0, HealingPhase.ACUTE),
        (1, HealingPhase.ACUTE),
        (6, HealingPhase.ACUTE),
        (7, HealingPhase.SUBACUTE),
        (14, HealingPhase.SUBACUTE),
        (20, HealingPhase.SUBACUTE),
        (21, HealingPhase.REMODELING),
        (45, HealingPhase.REMODELING),
        (89, HealingPhase.REMODELING),
        (90, HealingPhase.RETURN_TO_ACTIVITY),
        (120, HealingPhase.RETURN_TO_ACTIVITY),
        (365, HealingPhase.RETURN_TO_ACTIVITY),
    ])
    def test_phase_from_days(self, days: int, expected_phase: HealingPhase):
        """compute_phase(days) should return the correct phase."""
        assert compute_phase(days) == expected_phase

    def test_injury_computed_phase_uses_onset_date(self):
        """Injury.computed_phase() should compute from onset_date."""
        today = date(2026, 6, 6)
        # Onset 27 days ago (2026-05-10 to 2026-06-06)
        onset = date(2026, 5, 10)
        inj = _make_injury(onset)
        assert inj.computed_phase(today) == HealingPhase.REMODELING

    def test_days_since_onset_with_reference(self):
        """days_since_onset() should use the reference_date when provided."""
        onset = date(2026, 5, 10)
        ref = date(2026, 6, 6)
        inj = _make_injury(onset)
        assert inj.days_since_onset(ref) == 27

    def test_days_since_onset_zero_on_onset_day(self):
        """days_since_onset should be 0 when reference == onset."""
        onset = date(2026, 6, 1)
        inj = _make_injury(onset)
        assert inj.days_since_onset(date(2026, 6, 1)) == 0

    def test_phase_boundary_exact_day_7(self):
        """Exactly day 7 should be SUBACUTE (not ACUTE)."""
        onset = date(2026, 5, 30)
        ref = date(2026, 6, 6)  # 7 days later
        inj = _make_injury(onset)
        assert inj.computed_phase(ref) == HealingPhase.SUBACUTE

    def test_phase_boundary_exact_day_90(self):
        """Exactly day 90 should be RETURN_TO_ACTIVITY."""
        onset = date(2026, 3, 8)
        ref = date(2026, 6, 6)  # 90 days later
        inj = _make_injury(onset)
        assert inj.computed_phase(ref) == HealingPhase.RETURN_TO_ACTIVITY


# ---------------------------------------------------------------------------
# Phase override
# ---------------------------------------------------------------------------


class TestPhaseOverride:
    def test_override_takes_precedence_over_computed(self):
        """phase_override should trump the computed phase."""
        onset = date(2026, 5, 10)  # day 27 → remodeling
        inj = _make_injury(onset, phase_override=HealingPhase.SUBACUTE)
        ref = date(2026, 6, 6)
        assert inj.computed_phase(ref) == HealingPhase.SUBACUTE  # not REMODELING

    def test_no_override_returns_computed(self):
        """When phase_override is None, computed_phase uses the formula."""
        onset = date(2026, 5, 10)
        inj = _make_injury(onset, phase_override=None)
        ref = date(2026, 6, 6)
        assert inj.computed_phase(ref) == HealingPhase.REMODELING

    def test_override_with_rta(self):
        """Override to RTA should work even on a day-0 injury."""
        inj = _make_injury(date.today(), phase_override=HealingPhase.RETURN_TO_ACTIVITY)
        assert inj.computed_phase() == HealingPhase.RETURN_TO_ACTIVITY


# ---------------------------------------------------------------------------
# InjuryState validation
# ---------------------------------------------------------------------------


class TestInjuryStateValidation:
    def test_pain_scale_bounds(self):
        """subjective_pain must be 0-10."""
        base = {
            "injury_id": "x",
            "recorded_at": datetime.now(tz=timezone.utc),
            "inflammation": "mild",
            "pain_on": [],
            "load_tolerance_pct": 0.5,
        }
        # Valid bounds
        InjuryState(**{**base, "subjective_pain": 0})
        InjuryState(**{**base, "subjective_pain": 10})
        # Invalid
        with pytest.raises(Exception):
            InjuryState(**{**base, "subjective_pain": 11})
        with pytest.raises(Exception):
            InjuryState(**{**base, "subjective_pain": -1})

    def test_load_tolerance_bounds(self):
        """load_tolerance_pct must be 0.0-1.0."""
        base = {
            "injury_id": "x",
            "recorded_at": datetime.now(tz=timezone.utc),
            "inflammation": "mild",
            "pain_on": [],
            "subjective_pain": 3,
        }
        InjuryState(**{**base, "load_tolerance_pct": 0.0})
        InjuryState(**{**base, "load_tolerance_pct": 1.0})
        with pytest.raises(Exception):
            InjuryState(**{**base, "load_tolerance_pct": 1.1})
        with pytest.raises(Exception):
            InjuryState(**{**base, "load_tolerance_pct": -0.1})

    def test_naive_datetime_gets_utc(self):
        """Naive recorded_at should be treated as UTC."""
        naive_dt = datetime(2026, 6, 6, 8, 15, 0)
        state = InjuryState(
            injury_id="x",
            recorded_at=naive_dt,
            inflammation="none",
            pain_on=[],
            subjective_pain=2,
            load_tolerance_pct=0.7,
        )
        assert state.recorded_at.tzinfo is not None


# ---------------------------------------------------------------------------
# State time series methods
# ---------------------------------------------------------------------------


class TestInjuryStateTimeSeries:
    def test_current_state_returns_most_recent(self):
        """current_state() should return the most recently recorded state."""
        inj = _make_injury(date(2026, 5, 10))
        s1 = _make_state("test_inj", datetime(2026, 6, 5, 8, 0, tzinfo=timezone.utc))
        s2 = _make_state("test_inj", datetime(2026, 6, 6, 8, 15, tzinfo=timezone.utc))
        inj = inj.model_copy(update={"states": [s1, s2]})

        result = inj.current_state()
        assert result is not None
        assert result.recorded_at == s2.recorded_at

    def test_current_state_none_when_no_states(self):
        """current_state() returns None when no check-ins exist."""
        inj = _make_injury(date(2026, 5, 10))
        assert inj.current_state() is None

    def test_state_for_date_returns_on_or_before(self):
        """state_for_date() returns most recent state on or before target."""
        s1 = _make_state("test_inj", datetime(2026, 6, 5, 8, 0, tzinfo=timezone.utc))
        s2 = _make_state("test_inj", datetime(2026, 6, 6, 8, 15, tzinfo=timezone.utc))
        inj = _make_injury(date(2026, 5, 10))
        inj = inj.model_copy(update={"states": [s1, s2]})

        result = inj.state_for_date(date(2026, 6, 5))
        assert result is not None
        assert result.recorded_at == s1.recorded_at

    def test_state_for_date_none_when_before_all_states(self):
        """state_for_date() returns None when target date precedes all states."""
        s1 = _make_state("test_inj", datetime(2026, 6, 6, 8, tzinfo=timezone.utc))
        inj = _make_injury(date(2026, 5, 10))
        inj = inj.model_copy(update={"states": [s1]})

        result = inj.state_for_date(date(2026, 6, 5))
        assert result is None

    def test_has_checkin_today_true(self):
        """has_checkin_today() returns True when today's state exists."""
        today = date(2026, 6, 6)
        s = _make_state("test_inj", datetime(2026, 6, 6, 8, 15, tzinfo=timezone.utc))
        inj = _make_injury(date(2026, 5, 10))
        inj = inj.model_copy(update={"states": [s]})
        assert inj.has_checkin_today(today) is True

    def test_has_checkin_today_false(self):
        """has_checkin_today() returns False when no state recorded today."""
        today = date(2026, 6, 7)
        s = _make_state("test_inj", datetime(2026, 6, 6, 8, 15, tzinfo=timezone.utc))
        inj = _make_injury(date(2026, 5, 10))
        inj = inj.model_copy(update={"states": [s]})
        assert inj.has_checkin_today(today) is False

    def test_has_checkin_today_false_no_states(self):
        """has_checkin_today() returns False when there are no states at all."""
        inj = _make_injury(date(2026, 5, 10))
        assert inj.has_checkin_today(date.today()) is False


# ---------------------------------------------------------------------------
# Jordan Rivera's injury from seed data
# ---------------------------------------------------------------------------


class TestJordanInjuryFromSeedData:
    @pytest.fixture(scope="class")
    def jordan_injury_raw(self):
        """Load Jordan's injury from member-context.json."""
        member = load_member_context()
        raw = next(inj for inj in member.injuries if inj.id == "inj_knee_left")
        return raw

    def test_jordan_injury_loads(self, jordan_injury_raw):
        """Jordan's injury record loads without error."""
        assert jordan_injury_raw is not None
        assert jordan_injury_raw.id == "inj_knee_left"

    def test_jordan_injury_has_states(self, jordan_injury_raw):
        """Jordan's injury record includes 2 state history entries."""
        assert len(jordan_injury_raw.states) == 2

    def test_jordan_injury_onset_date(self, jordan_injury_raw):
        """Jordan's onset_date is 2026-05-10."""
        onset = jordan_injury_raw.onset_date or jordan_injury_raw.since
        assert onset is not None
        assert "2026-05-10" in str(onset)

    def test_jordan_in_remodeling_phase(self, jordan_injury_raw):
        """Jordan is in remodeling phase on 2026-06-06 (day 27 since onset)."""
        from app.api.routes.injury import _promote_injury
        injury = _promote_injury(jordan_injury_raw, "mbr_01HX9JORDAN")
        assert injury.computed_phase(date(2026, 6, 6)) == HealingPhase.REMODELING

    def test_jordan_current_state_is_june_6(self, jordan_injury_raw):
        """Jordan's most recent check-in is from 2026-06-06."""
        from app.api.routes.injury import _promote_injury
        injury = _promote_injury(jordan_injury_raw, "mbr_01HX9JORDAN")
        current = injury.current_state()
        assert current is not None
        assert current.recorded_at.date() == date(2026, 6, 6)

    def test_jordan_current_state_pain_on_flexion(self, jordan_injury_raw):
        """Jordan's June 6 state has 'flexion' in pain_on."""
        from app.api.routes.injury import _promote_injury
        injury = _promote_injury(jordan_injury_raw, "mbr_01HX9JORDAN")
        current = injury.current_state()
        assert current is not None
        assert "flexion" in current.pain_on

    def test_jordan_load_tolerance_70pct(self, jordan_injury_raw):
        """Jordan's June 6 load tolerance is 0.7."""
        from app.api.routes.injury import _promote_injury
        injury = _promote_injury(jordan_injury_raw, "mbr_01HX9JORDAN")
        current = injury.current_state()
        assert current is not None
        assert current.load_tolerance_pct == pytest.approx(0.7)
