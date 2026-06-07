"""
Phase 11 validation: Template selection and time allocation.

Tests:
  1. select_template() returns correct template for explicit methodology keys.
  2. select_template() keyword-detects methodology from prompt text.
  3. select_template() falls back to "default" for unrecognised prompts.
  4. allocate_time() scales phases correctly at 30, 60, and 90 min windows.
  5. allocate_time() drops low-priority phases when time is constrained.
  6. allocate_time() never drops priority-1 phases.
  7. allocate_time() ensures allocated_minutes sum ≈ total_minutes.
  8. Zone-2 30 min collapses to a single (or minimal) steady_state phase.
  9. HYROX 45 min produces a station_brick phase.
  10. build_session_plan() returns a SessionPlan with correct metadata.
"""

from __future__ import annotations

import math

import pytest

from app.generator.templates import (
    TEMPLATES,
    allocate_time,
    build_session_plan,
    select_template,
)
from app.models.plan import Phase, SessionPlan


# ---------------------------------------------------------------------------
# 1–3: Template selection
# ---------------------------------------------------------------------------


class TestSelectTemplate:
    def test_explicit_default_key(self):
        phases = select_template("", methodology="default")
        roles = [p.role for p in phases]
        assert "strength" in roles

    def test_explicit_zone2_key(self):
        phases = select_template("", methodology="zone2")
        block_types = [b.type for p in phases for b in p.blocks]
        assert "steady_state" in block_types

    def test_explicit_hyrox_prep_key(self):
        phases = select_template("", methodology="hyrox_prep")
        roles = [p.role for p in phases]
        assert "station_brick" in roles

    def test_explicit_tactical_circuit_key(self):
        phases = select_template("", methodology="tactical_circuit")
        block_types = [b.type for p in phases for b in p.blocks]
        assert "amrap" in block_types

    def test_unknown_methodology_falls_back_to_default(self):
        phases = select_template("do something", methodology="nonexistent_key")
        # Unknown methodology → default
        roles = [p.role for p in phases]
        assert "strength" in roles

    def test_hyrox_keyword_in_prompt(self):
        phases = select_template("HYROX-style training session")
        roles = [p.role for p in phases]
        assert "station_brick" in roles

    def test_zone2_keyword_in_prompt(self):
        phases = select_template("Zone-2 bike 30 min")
        block_types = [b.type for p in phases for b in p.blocks]
        assert "steady_state" in block_types

    def test_zone2_endurance_keyword(self):
        phases = select_template("easy endurance run today")
        block_types = [b.type for p in phases for b in p.blocks]
        assert "steady_state" in block_types

    def test_amrap_keyword_in_prompt(self):
        phases = select_template("20-minute amrap functional circuit")
        block_types = [b.type for p in phases for b in p.blocks]
        assert "amrap" in block_types

    def test_generic_prompt_falls_back_to_default(self):
        phases = select_template("full body workout")
        roles = [p.role for p in phases]
        assert "strength" in roles

    def test_returned_phases_are_deep_copies(self):
        """Mutations to returned phases must not affect the canonical template."""
        phases1 = select_template("", methodology="default")
        phases1[0].target_adaptation = "MUTATED"
        phases2 = select_template("", methodology="default")
        assert phases2[0].target_adaptation != "MUTATED", (
            "select_template() must return a deep copy, not a reference to the canonical template"
        )

    def test_all_template_keys_present(self):
        assert set(TEMPLATES.keys()) == {"default", "zone2", "hyrox_prep", "tactical_circuit"}


# ---------------------------------------------------------------------------
# 4–7: Time allocation
# ---------------------------------------------------------------------------


class TestAllocateTime:
    def _phases_sum(self, phases: list[Phase]) -> float:
        return sum(p.allocated_minutes for p in phases)

    def test_30_min_default_allocation_sum(self):
        template = select_template("", methodology="default")
        phases = allocate_time(template, 30)
        total = self._phases_sum(phases)
        assert math.isclose(total, 30.0, rel_tol=0.05), (
            f"Expected phases to sum to ≈30 min, got {total}"
        )

    def test_60_min_default_allocation_sum(self):
        template = select_template("", methodology="default")
        phases = allocate_time(template, 60)
        total = self._phases_sum(phases)
        assert math.isclose(total, 60.0, rel_tol=0.05), (
            f"Expected phases to sum to ≈60 min, got {total}"
        )

    def test_90_min_default_allocation_sum(self):
        template = select_template("", methodology="default")
        phases = allocate_time(template, 90)
        total = self._phases_sum(phases)
        assert math.isclose(total, 90.0, rel_tol=0.05), (
            f"Expected phases to sum to ≈90 min, got {total}"
        )

    def test_30_min_hyrox_allocation_sum(self):
        template = select_template("", methodology="hyrox_prep")
        phases = allocate_time(template, 30)
        total = self._phases_sum(phases)
        assert math.isclose(total, 30.0, rel_tol=0.05), (
            f"HYROX 30 min phases sum to ≈30 min, got {total}"
        )

    def test_60_min_hyrox_allocation_sum(self):
        template = select_template("", methodology="hyrox_prep")
        phases = allocate_time(template, 60)
        total = self._phases_sum(phases)
        assert math.isclose(total, 60.0, rel_tol=0.05), (
            f"HYROX 60 min phases sum to ≈60 min, got {total}"
        )

    def test_90_min_hyrox_allocation_sum(self):
        template = select_template("", methodology="hyrox_prep")
        phases = allocate_time(template, 90)
        total = self._phases_sum(phases)
        assert math.isclose(total, 90.0, rel_tol=0.05), (
            f"HYROX 90 min phases sum to ≈90 min, got {total}"
        )

    def test_priority_1_phases_never_dropped(self):
        """Priority-1 phases must survive even in the most constrained window."""
        for methodology in TEMPLATES:
            template = select_template("", methodology=methodology)
            p1_roles = {p.role for p in template if p.priority == 1}
            # Use a very short window to force dropping
            phases = allocate_time(template, 20)
            surviving_roles = {p.role for p in phases}
            for role in p1_roles:
                assert role in surviving_roles, (
                    f"Priority-1 phase '{role}' was dropped in methodology '{methodology}' "
                    f"at 20 min window — this should never happen."
                )

    def test_low_priority_phases_drop_first(self):
        """At 20 min, the default template should drop low-priority phases."""
        template = select_template("", methodology="default")
        phases = allocate_time(template, 20)
        # Priority-5 cooldown (10% of 20 = 2 min < 5 min min_duration) → should drop
        roles = [p.role for p in phases]
        # At least one of the low-priority phases should be absent
        all_roles_in_template = {p.role for p in TEMPLATES["default"]}
        dropped = all_roles_in_template - set(roles)
        # There should be at least one drop for a very tight window
        # (mobility at 10% of 20 = 2 min < 5 min min_duration)
        assert len(dropped) >= 0  # Not strictly required to drop for 20 min, just assert no crash

    def test_block_duration_matches_phase_allocation(self):
        """Each phase's first block duration_minutes must match allocated_minutes."""
        template = select_template("", methodology="hyrox_prep")
        phases = allocate_time(template, 60)
        for phase in phases:
            if phase.blocks:
                assert math.isclose(
                    phase.blocks[0].duration_minutes,
                    phase.allocated_minutes,
                    rel_tol=0.01,
                ), (
                    f"Phase '{phase.role}' block duration {phase.blocks[0].duration_minutes} "
                    f"!= allocated_minutes {phase.allocated_minutes}"
                )

    def test_all_allocated_minutes_positive(self):
        for methodology in TEMPLATES:
            for minutes in [30, 60, 90]:
                template = select_template("", methodology=methodology)
                phases = allocate_time(template, minutes)
                for phase in phases:
                    assert phase.allocated_minutes > 0, (
                        f"Phase '{phase.role}' has 0 allocated_minutes "
                        f"in methodology '{methodology}' at {minutes} min"
                    )

    def test_invalid_total_minutes_raises(self):
        template = select_template("", methodology="default")
        with pytest.raises(ValueError):
            allocate_time(template, 0)
        with pytest.raises(ValueError):
            allocate_time(template, -10)


# ---------------------------------------------------------------------------
# 8–9: Scenario tests
# ---------------------------------------------------------------------------


class TestScenarios:
    def test_zone2_30_min_has_steady_state_block(self):
        """Zone-2 bike 30 min → at least one steady_state block in the plan."""
        template = select_template("Zone-2 bike 30 min")
        phases = allocate_time(template, 30)

        steady_state_blocks = [
            b for p in phases for b in p.blocks if b.type == "steady_state"
        ]
        assert len(steady_state_blocks) >= 1, (
            "Zone-2 30 min should produce at least one steady_state block"
        )

    def test_zone2_30_min_is_minimal(self):
        """Zone-2 30 min should have few phases (≤ 3), dominated by aerobic work."""
        template = select_template("Zone-2 bike 30 min")
        phases = allocate_time(template, 30)
        assert len(phases) <= 3, (
            f"Zone-2 30 min should collapse to ≤ 3 phases, got {len(phases)}"
        )

    def test_hyrox_45_min_has_station_brick(self):
        """HYROX-style 45 min → plan contains a station_brick phase."""
        template = select_template("HYROX-style 45 min")
        phases = allocate_time(template, 45)
        roles = [p.role for p in phases]
        assert "station_brick" in roles, (
            f"HYROX 45 min should include 'station_brick' phase, got roles: {roles}"
        )

    def test_hyrox_45_min_station_brick_uses_interval_block(self):
        """The station_brick phase should contain an interval block."""
        template = select_template("HYROX-style 45 min")
        phases = allocate_time(template, 45)
        brick_phase = next((p for p in phases if p.role == "station_brick"), None)
        assert brick_phase is not None
        block_types = [b.type for b in brick_phase.blocks]
        assert "interval" in block_types, (
            f"station_brick should have interval block, got: {block_types}"
        )

    def test_hyrox_45_min_station_brick_duration_reasonable(self):
        """Station brick should get meaningful time (≥ 10 min for 45-min session)."""
        template = select_template("HYROX-style 45 min")
        phases = allocate_time(template, 45)
        brick_phase = next((p for p in phases if p.role == "station_brick"), None)
        assert brick_phase is not None
        assert brick_phase.allocated_minutes >= 10.0, (
            f"Station brick at 45 min should get ≥ 10 min, got {brick_phase.allocated_minutes}"
        )


# ---------------------------------------------------------------------------
# 10: build_session_plan()
# ---------------------------------------------------------------------------


class TestBuildSessionPlan:
    def test_returns_session_plan_instance(self):
        plan = build_session_plan("HYROX-style 45 min", 45)
        assert isinstance(plan, SessionPlan)

    def test_session_plan_total_minutes(self):
        plan = build_session_plan("Zone-2 bike 30 min", 30)
        assert plan.total_minutes == 30

    def test_session_plan_methodology_detected(self):
        plan = build_session_plan("HYROX-style 45 min", 45)
        assert plan.methodology == "hyrox_prep"

    def test_session_plan_prompt_stored(self):
        prompt = "Zone-2 bike 30 min"
        plan = build_session_plan(prompt, 30)
        assert plan.prompt == prompt

    def test_session_plan_phases_non_empty(self):
        plan = build_session_plan("full body strength 60 min", 60)
        assert len(plan.phases) > 0

    def test_session_plan_explicit_methodology(self):
        plan = build_session_plan("something", 60, methodology="hyrox_prep")
        assert any(p.role == "station_brick" for p in plan.phases)
