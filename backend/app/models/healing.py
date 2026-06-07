"""
Healing phase rules and load tolerance curves — Phase 5.

Defines:
  - PHASE_THRESHOLDS: day ranges for each phase
  - PHASE_RESTRICTIONS: movement type exclusions and load caps per phase
  - compute_phase(): derive phase from days since onset
  - phase_load_tolerance_curve(): smooth load tolerance within a phase

The design uses fixed day-count thresholds as the MVP.  Injury-specific
thresholds and coach overrides are handled in the Injury model itself
(phase_override field); this module only codifies the default progression.
"""

from __future__ import annotations

import math
from typing import Any

from app.models.injury import HealingPhase

# ---------------------------------------------------------------------------
# Phase thresholds (start_day inclusive, end_day exclusive)
# ---------------------------------------------------------------------------

PHASE_THRESHOLDS: dict[HealingPhase, tuple[int, float]] = {
    HealingPhase.ACUTE: (0, 7),
    HealingPhase.SUBACUTE: (7, 21),
    HealingPhase.REMODELING: (21, 90),
    HealingPhase.RETURN_TO_ACTIVITY: (90, math.inf),
}

# ---------------------------------------------------------------------------
# Phase restrictions
# ---------------------------------------------------------------------------

#: Movement types that are excluded in each phase (applied at the injured joint).
#: Exercises performing these movement types at the injured joint are removed
#: regardless of the member's check-in state (minimum safety floor).
#:
#: Additionally, check-in pain_on list can add *more* exclusions on top.
PHASE_RESTRICTIONS: dict[HealingPhase, dict[str, Any]] = {
    HealingPhase.ACUTE: {
        "excluded_movement_types": ["load", "impact", "rotation"],
        "max_load_tolerance": 0.0,   # absolutely no loading
        "allowed_movement_types": ["flexion", "extension"],  # passive ROM only
        "description": "Acute phase: protect the injury, no loading or impact.",
    },
    HealingPhase.SUBACUTE: {
        "excluded_movement_types": ["impact"],
        "max_load_tolerance": 0.3,   # up to 30% normal load
        "allowed_movement_types": ["flexion", "extension", "rotation", "load"],
        "description": "Subacute phase: gentle ROM and very light loading only.",
    },
    HealingPhase.REMODELING: {
        "excluded_movement_types": [],   # all types potentially allowed
        "max_load_tolerance": 0.8,        # up to 80% normal load
        "allowed_movement_types": ["flexion", "extension", "rotation", "load", "impact"],
        "description": "Remodeling phase: progressive loading; light impact allowed.",
    },
    HealingPhase.RETURN_TO_ACTIVITY: {
        "excluded_movement_types": [],
        "max_load_tolerance": 1.0,        # full load permitted
        "allowed_movement_types": ["flexion", "extension", "rotation", "load", "impact"],
        "description": "Return-to-activity: progressive loading toward full capacity.",
    },
}

# ---------------------------------------------------------------------------
# compute_phase()
# ---------------------------------------------------------------------------


def compute_phase(days_since_onset: int) -> HealingPhase:
    """
    Derive the healing phase from the number of days since injury onset.

    Uses fixed thresholds (MVP approach).  Coach/PT overrides are applied
    separately via Injury.computed_phase().

    Parameters
    ----------
    days_since_onset:
        Calendar days since the injury onset date (0-indexed: same day = 0).

    Returns
    -------
    HealingPhase
    """
    if days_since_onset < 7:
        return HealingPhase.ACUTE
    elif days_since_onset < 21:
        return HealingPhase.SUBACUTE
    elif days_since_onset < 90:
        return HealingPhase.REMODELING
    else:
        return HealingPhase.RETURN_TO_ACTIVITY


# ---------------------------------------------------------------------------
# phase_load_tolerance_curve()
# ---------------------------------------------------------------------------


def phase_load_tolerance_curve(phase: HealingPhase, day_in_phase: int) -> float:
    """
    Return the recommended load tolerance (0.0-1.0) for a given day within
    a healing phase.

    The curve is a smooth sigmoid-style ramp within the phase's day window,
    bounded by the phase's max_load_tolerance.

    day_in_phase is 0-indexed: 0 = first day of that phase.

    Design intent:
      - Acute (days 0-6 in phase): starts at 0.0, ends at 0.0 — no loading
      - Subacute (days 0-13 in phase): 0.05 → 0.30 linear ramp
      - Remodeling (days 0-68 in phase): 0.30 → 0.80 gradual sigmoid
      - RTA (days 0+ in phase): 0.80 → 1.0 gradual ramp, caps at 1.0
    """
    restrictions = PHASE_RESTRICTIONS[phase]
    max_tol = restrictions["max_load_tolerance"]

    if phase == HealingPhase.ACUTE:
        # No loading during acute phase
        return 0.0

    elif phase == HealingPhase.SUBACUTE:
        # Linear ramp over 14 days from 0.05 to max_tol (0.30)
        phase_duration = 14
        progress = min(day_in_phase / max(phase_duration - 1, 1), 1.0)
        return round(0.05 + progress * (max_tol - 0.05), 3)

    elif phase == HealingPhase.REMODELING:
        # Sigmoid ramp over 69 days from 0.30 to max_tol (0.80)
        phase_duration = 69
        progress = min(day_in_phase / max(phase_duration - 1, 1), 1.0)
        # Smooth sigmoid: f(x) = 1 / (1 + e^(-10*(x - 0.5)))
        sigmoid = 1.0 / (1.0 + math.exp(-10 * (progress - 0.5)))
        # Scale sigmoid (output is ~0.007 to ~0.993) to 0.30 → 0.80 range
        low, high = 0.30, max_tol
        return round(low + sigmoid * (high - low), 3)

    else:  # RETURN_TO_ACTIVITY
        # Gradual linear ramp from 0.80 toward 1.0 over 60 days, then hold at 1.0
        ramp_days = 60
        start_tol = 0.80
        progress = min(day_in_phase / ramp_days, 1.0)
        return round(start_tol + progress * (1.0 - start_tol), 3)


# ---------------------------------------------------------------------------
# day_in_phase()
# ---------------------------------------------------------------------------


def day_in_phase(days_since_onset: int, phase: HealingPhase) -> int:
    """
    Return how many days the member has been in the given phase.

    day_in_phase is 0-indexed: 0 = first day of that phase.

    Clamps to 0 for edge cases where days_since_onset precedes the phase start.
    """
    phase_start, _phase_end = PHASE_THRESHOLDS[phase]
    return max(0, days_since_onset - int(phase_start))
