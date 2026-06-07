"""
Phase 5 validation: Healing Phase Load Tolerance Curves

Tests cover:
  1. phase_load_tolerance_curve() returns 0.0 for all of acute phase
  2. Subacute curve starts at ~0.05 and ends at ~0.30
  3. Remodeling curve is monotonically non-decreasing
  4. RTA curve starts at 0.80 and reaches 1.0 by day 60
  5. All curve values are within [0.0, 1.0]
  6. day_in_phase() computes correct offset within phase
  7. PHASE_RESTRICTIONS max_load_tolerance is consistent with curve endpoints
"""

from __future__ import annotations

import pytest

from app.models.healing import (
    PHASE_RESTRICTIONS,
    PHASE_THRESHOLDS,
    HealingPhase,
    compute_phase,
    day_in_phase,
    phase_load_tolerance_curve,
)


# ---------------------------------------------------------------------------
# Acute phase — zero loading
# ---------------------------------------------------------------------------


class TestAcuteCurve:
    @pytest.mark.parametrize("day", [0, 1, 3, 6])
    def test_acute_curve_is_zero(self, day: int):
        """Acute phase curve must be 0.0 at every day — no loading allowed."""
        result = phase_load_tolerance_curve(HealingPhase.ACUTE, day)
        assert result == 0.0, f"Expected 0.0 for acute day {day}, got {result}"

    def test_acute_max_load_restriction_is_zero(self):
        """PHASE_RESTRICTIONS[ACUTE].max_load_tolerance must be 0.0."""
        restrictions = PHASE_RESTRICTIONS[HealingPhase.ACUTE]
        assert restrictions["max_load_tolerance"] == 0.0

    def test_acute_excluded_movement_types(self):
        """Acute phase must exclude load and impact movement types."""
        restrictions = PHASE_RESTRICTIONS[HealingPhase.ACUTE]
        excluded = set(restrictions["excluded_movement_types"])
        assert "load" in excluded
        assert "impact" in excluded


# ---------------------------------------------------------------------------
# Subacute phase — gentle loading ramp
# ---------------------------------------------------------------------------


class TestSubacuteCurve:
    def test_subacute_starts_above_zero(self):
        """Subacute curve should start above 0.0 (gentle loading begins)."""
        result = phase_load_tolerance_curve(HealingPhase.SUBACUTE, 0)
        assert result > 0.0, "Subacute day 0 should be > 0"

    def test_subacute_ends_at_max_tolerance(self):
        """Subacute curve endpoint should reach max_load_tolerance (0.30)."""
        max_tol = PHASE_RESTRICTIONS[HealingPhase.SUBACUTE]["max_load_tolerance"]
        # day 13 = last day of a 14-day phase window
        result = phase_load_tolerance_curve(HealingPhase.SUBACUTE, 13)
        assert result == pytest.approx(max_tol, abs=0.01), (
            f"Subacute day 13 should be ~{max_tol}, got {result}"
        )

    def test_subacute_monotonically_increasing(self):
        """Subacute curve must be monotonically non-decreasing over 14 days."""
        values = [phase_load_tolerance_curve(HealingPhase.SUBACUTE, d) for d in range(14)]
        for i in range(1, len(values)):
            assert values[i] >= values[i - 1], (
                f"Subacute curve decreased at day {i}: {values[i - 1]} → {values[i]}"
            )

    def test_subacute_max_restriction_is_030(self):
        """PHASE_RESTRICTIONS[SUBACUTE].max_load_tolerance should be 0.30."""
        restrictions = PHASE_RESTRICTIONS[HealingPhase.SUBACUTE]
        assert restrictions["max_load_tolerance"] == pytest.approx(0.30)

    def test_subacute_excludes_impact(self):
        """Subacute phase must still exclude impact movements."""
        restrictions = PHASE_RESTRICTIONS[HealingPhase.SUBACUTE]
        assert "impact" in restrictions["excluded_movement_types"]

    def test_subacute_does_not_exclude_flexion(self):
        """Subacute phase should allow flexion (gentle ROM work)."""
        restrictions = PHASE_RESTRICTIONS[HealingPhase.SUBACUTE]
        assert "flexion" not in restrictions["excluded_movement_types"]


# ---------------------------------------------------------------------------
# Remodeling phase — progressive loading
# ---------------------------------------------------------------------------


class TestRemodelingCurve:
    def test_remodeling_starts_above_subacute_end(self):
        """Remodeling day 0 should be >= subacute max (~0.30)."""
        result = phase_load_tolerance_curve(HealingPhase.REMODELING, 0)
        assert result >= 0.30, f"Remodeling day 0 should be >= 0.30, got {result}"

    def test_remodeling_ends_near_max_tolerance(self):
        """Remodeling day 68 should reach max_load_tolerance (0.80)."""
        max_tol = PHASE_RESTRICTIONS[HealingPhase.REMODELING]["max_load_tolerance"]
        result = phase_load_tolerance_curve(HealingPhase.REMODELING, 68)
        assert result == pytest.approx(max_tol, abs=0.02), (
            f"Remodeling day 68 should be ~{max_tol}, got {result}"
        )

    def test_remodeling_monotonically_increasing(self):
        """Remodeling curve must be monotonically non-decreasing over 69 days."""
        values = [phase_load_tolerance_curve(HealingPhase.REMODELING, d) for d in range(69)]
        for i in range(1, len(values)):
            assert values[i] >= values[i - 1], (
                f"Remodeling curve decreased at day {i}: {values[i - 1]} → {values[i]}"
            )

    def test_remodeling_max_restriction_is_080(self):
        """PHASE_RESTRICTIONS[REMODELING].max_load_tolerance should be 0.80."""
        restrictions = PHASE_RESTRICTIONS[HealingPhase.REMODELING]
        assert restrictions["max_load_tolerance"] == pytest.approx(0.80)

    def test_remodeling_no_phase_level_exclusions(self):
        """Remodeling phase should have no movement-type exclusions at phase level."""
        restrictions = PHASE_RESTRICTIONS[HealingPhase.REMODELING]
        assert restrictions["excluded_movement_types"] == []


# ---------------------------------------------------------------------------
# Return-to-activity phase — full loading
# ---------------------------------------------------------------------------


class TestRTACurve:
    def test_rta_starts_at_080(self):
        """RTA curve day 0 should start at 0.80."""
        result = phase_load_tolerance_curve(HealingPhase.RETURN_TO_ACTIVITY, 0)
        assert result == pytest.approx(0.80, abs=0.01), (
            f"RTA day 0 should be ~0.80, got {result}"
        )

    def test_rta_reaches_1_by_day_60(self):
        """RTA curve should reach 1.0 by day 60."""
        result = phase_load_tolerance_curve(HealingPhase.RETURN_TO_ACTIVITY, 60)
        assert result == pytest.approx(1.0, abs=0.01), (
            f"RTA day 60 should be ~1.0, got {result}"
        )

    def test_rta_does_not_exceed_1(self):
        """RTA curve must never exceed 1.0 (tested up to day 120)."""
        for d in range(0, 121):
            result = phase_load_tolerance_curve(HealingPhase.RETURN_TO_ACTIVITY, d)
            assert result <= 1.0, f"RTA day {d} exceeded 1.0: {result}"

    def test_rta_monotonically_non_decreasing(self):
        """RTA curve must be monotonically non-decreasing from day 0 to 60."""
        values = [
            phase_load_tolerance_curve(HealingPhase.RETURN_TO_ACTIVITY, d)
            for d in range(61)
        ]
        for i in range(1, len(values)):
            assert values[i] >= values[i - 1], (
                f"RTA curve decreased at day {i}: {values[i - 1]} → {values[i]}"
            )

    def test_rta_max_restriction_is_1(self):
        """PHASE_RESTRICTIONS[RTA].max_load_tolerance should be 1.0."""
        restrictions = PHASE_RESTRICTIONS[HealingPhase.RETURN_TO_ACTIVITY]
        assert restrictions["max_load_tolerance"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# All curves produce values in [0, 1]
# ---------------------------------------------------------------------------


class TestCurveBounds:
    @pytest.mark.parametrize("phase,max_day", [
        (HealingPhase.ACUTE, 7),
        (HealingPhase.SUBACUTE, 14),
        (HealingPhase.REMODELING, 69),
        (HealingPhase.RETURN_TO_ACTIVITY, 120),
    ])
    def test_curve_values_in_range(self, phase: HealingPhase, max_day: int):
        """All curve values must be in [0.0, 1.0]."""
        for d in range(max_day):
            v = phase_load_tolerance_curve(phase, d)
            assert 0.0 <= v <= 1.0, f"{phase.value} day {d} out of range: {v}"


# ---------------------------------------------------------------------------
# day_in_phase()
# ---------------------------------------------------------------------------


class TestDayInPhase:
    def test_day_in_phase_subacute_day_0(self):
        """Day 7 since onset is day 0 in subacute."""
        result = day_in_phase(7, HealingPhase.SUBACUTE)
        assert result == 0

    def test_day_in_phase_subacute_day_7(self):
        """Day 14 since onset is day 7 in subacute."""
        result = day_in_phase(14, HealingPhase.SUBACUTE)
        assert result == 7

    def test_day_in_phase_remodeling_day_0(self):
        """Day 21 since onset is day 0 in remodeling."""
        result = day_in_phase(21, HealingPhase.REMODELING)
        assert result == 0

    def test_day_in_phase_remodeling_day_6(self):
        """Day 27 since onset (Jordan's case) is day 6 in remodeling."""
        result = day_in_phase(27, HealingPhase.REMODELING)
        assert result == 6

    def test_day_in_phase_clamps_to_zero(self):
        """day_in_phase should not return negative values."""
        # Day 0 since onset asked for RTA phase (which starts at day 90)
        result = day_in_phase(0, HealingPhase.RETURN_TO_ACTIVITY)
        assert result == 0


# ---------------------------------------------------------------------------
# PHASE_THRESHOLDS structure
# ---------------------------------------------------------------------------


class TestPhaseThresholds:
    def test_all_phases_present(self):
        """All four phases should be in PHASE_THRESHOLDS."""
        for phase in HealingPhase:
            assert phase in PHASE_THRESHOLDS

    def test_thresholds_non_overlapping(self):
        """Phase threshold ranges should not overlap."""
        sorted_phases = sorted(PHASE_THRESHOLDS.items(), key=lambda x: x[1][0])
        for i in range(1, len(sorted_phases)):
            prev_phase, (prev_start, prev_end) = sorted_phases[i - 1]
            curr_phase, (curr_start, curr_end) = sorted_phases[i]
            assert curr_start == prev_end, (
                f"Gap or overlap between {prev_phase.value} "
                f"(ends {prev_end}) and {curr_phase.value} (starts {curr_start})"
            )

    def test_acute_starts_at_zero(self):
        """Acute phase must start at day 0."""
        start, _ = PHASE_THRESHOLDS[HealingPhase.ACUTE]
        assert start == 0
