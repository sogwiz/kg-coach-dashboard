"""
Dynamic Injury Model — Phase 5.

Provides:
  - HealingPhase enum (acute → subacute → remodeling → return-to-activity)
  - InjuryState: a single daily check-in snapshot
  - Injury: the full injury record with state time series and phase computation

The model is deliberately separate from the original thin Injury stub in
member.py so that the MemberContext JSON can carry either representation.
The loader coerces the richer format transparently.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Healing phase enum
# ---------------------------------------------------------------------------


class HealingPhase(str, Enum):
    ACUTE = "acute"               # Days 0-7: inflammation, protection
    SUBACUTE = "subacute"         # Days 7-21: repair begins, gentle ROM
    REMODELING = "remodeling"     # Days 21-90: tissue strengthening
    RETURN_TO_ACTIVITY = "rta"    # Day 90+: progressive loading


# Movement type literal — shared with Exercise model
MovementTypeLiteral = Literal["flexion", "extension", "rotation", "load", "impact"]

# ---------------------------------------------------------------------------
# InjuryState — a single daily check-in snapshot
# ---------------------------------------------------------------------------


class InjuryState(BaseModel):
    """
    A point-in-time snapshot of how an injury feels today.

    Recorded by the member (or coach) during the daily check-in flow.
    Multiple states build up a time series that tracks healing progress.
    """

    injury_id: str
    recorded_at: datetime
    inflammation: Literal["none", "mild", "moderate", "severe"]
    pain_on: list[MovementTypeLiteral] = Field(default_factory=list)
    subjective_pain: int = Field(ge=0, le=10)  # 0-10 scale
    load_tolerance_pct: float = Field(ge=0.0, le=1.0)  # 0.0-1.0
    notes: str | None = None

    @field_validator("recorded_at", mode="before")
    @classmethod
    def _normalise_tz(cls, v: object) -> object:
        """Ensure recorded_at is timezone-aware (default to UTC if naive)."""
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class InjuryStateCreate(BaseModel):
    """
    Input model for the check-in API endpoint.

    injury_id is injected server-side from the URL path parameter; the
    client only needs to supply the observation fields.
    """

    inflammation: Literal["none", "mild", "moderate", "severe"]
    pain_on: list[MovementTypeLiteral] = Field(default_factory=list)
    subjective_pain: int = Field(ge=0, le=10)
    load_tolerance_pct: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


# ---------------------------------------------------------------------------
# Injury — the full record with state time series
# ---------------------------------------------------------------------------


class Injury(BaseModel):
    """
    A member's injury record.

    Carries both the static metadata (what, when, where) and a time series
    of daily check-in states.  The healing phase is computed from days since
    onset but can be overridden by a coach or PT.
    """

    id: str
    region: str                        # e.g. "left knee"
    joint: str                         # catalog slug, e.g. "knee"
    diagnosis: str                     # human-readable, e.g. "patellofemoral pain syndrome"
    snomed_code: str | None = None     # optional SNOMED CT code
    onset_date: date
    current_phase: HealingPhase        # derived or overridden phase stored here
    phase_override: HealingPhase | None = None  # coach / PT can lock phase
    states: list[InjuryState] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Computed helpers
    # ------------------------------------------------------------------

    def days_since_onset(self, reference_date: date | None = None) -> int:
        """
        Return the number of calendar days since onset_date.

        Uses today's date by default; callers can supply a reference_date
        for deterministic testing.
        """
        ref = reference_date or date.today()
        return (ref - self.onset_date).days

    def computed_phase(self, reference_date: date | None = None) -> HealingPhase:
        """
        Derive the healing phase from days since onset using fixed thresholds.

        If phase_override is set, that takes precedence over the computation.
        """
        if self.phase_override is not None:
            return self.phase_override

        days = self.days_since_onset(reference_date)

        if days < 7:
            return HealingPhase.ACUTE
        elif days < 21:
            return HealingPhase.SUBACUTE
        elif days < 90:
            return HealingPhase.REMODELING
        else:
            return HealingPhase.RETURN_TO_ACTIVITY

    def current_state(self) -> InjuryState | None:
        """
        Return the most recent InjuryState, or None if no check-ins recorded.

        States are sorted by recorded_at descending; returns the first element.
        """
        if not self.states:
            return None
        return max(self.states, key=lambda s: s.recorded_at)

    def state_for_date(self, target_date: date) -> InjuryState | None:
        """
        Return the most recent state recorded on or before target_date, or None.

        Useful for "what was the state yesterday?" queries.
        """
        eligible = [
            s for s in self.states
            if s.recorded_at.date() <= target_date
        ]
        if not eligible:
            return None
        return max(eligible, key=lambda s: s.recorded_at)

    def has_checkin_today(self, reference_date: date | None = None) -> bool:
        """Return True if there is at least one check-in recorded today."""
        ref = reference_date or date.today()
        return any(s.recorded_at.date() == ref for s in self.states)
