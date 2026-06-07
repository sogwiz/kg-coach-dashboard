"""
Session templates — Phase 11 (Advanced Formats: Phases, Blocks, Hybrid Catalog).

Defines methodology-specific session templates as ordered lists of Phase
objects.  Each template captures the role, time_share, min_duration, and
priority of each phase.

Templates
---------
  "default"         — General-purpose strength + conditioning session
  "zone2"           — Low-intensity aerobic work (single steady_state phase)
  "hyrox_prep"      — HYROX race preparation (station_brick + strength + metcon)
  "tactical_circuit" — Tactical / functional-fitness circuit

Public API
----------
  select_template(prompt, methodology)        → list[Phase]
  allocate_time(template, total_minutes)      → list[Phase]

Design notes
------------
  - Templates use copy() to avoid mutation of the canonical definitions.
  - allocate_time() scales each phase by its time_share.  Phases whose
    scaled duration < min_duration are dropped in ascending priority order
    (priority 5 first, priority 1 never dropped) until the session fits.
  - The returned phases always sum to ≤ total_minutes.
  - Block-level exercise ids are intentionally empty in the template
    definitions — the generator fills them from the safe exercise set.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from app.models.plan import Block, Phase, SessionPlan


# ---------------------------------------------------------------------------
# Canonical template definitions
#
# Each entry is a list[Phase] used as a blueprint.  allocate_time() converts
# time_share values into concrete allocated_minutes for the requested window.
# ---------------------------------------------------------------------------


def _phase(
    role: str,
    target_adaptation: str,
    time_share: float,
    min_duration: int,
    priority: int,
    block_type: str = "strength",
    block_notes: str = "",
) -> Phase:
    """Helper to build a Phase with a single placeholder Block."""
    block = Block(
        type=block_type,  # type: ignore[arg-type]
        duration_minutes=0.0,   # filled in by allocate_time()
        notes=block_notes,
    )
    return Phase(
        role=role,  # type: ignore[arg-type]
        target_adaptation=target_adaptation,
        time_share=time_share,
        min_duration=min_duration,
        priority=priority,
        blocks=[block],
    )


# ---- default: general-purpose session ----
_DEFAULT_TEMPLATE: list[Phase] = [
    _phase(
        role="mobility",
        target_adaptation="joint prep and CNS activation",
        time_share=0.10,
        min_duration=5,
        priority=3,
        block_type="circuit",
        block_notes="Dynamic mobility and joint circles",
    ),
    _phase(
        role="strength",
        target_adaptation="muscular strength and hypertrophy",
        time_share=0.55,
        min_duration=20,
        priority=1,
        block_type="strength",
        block_notes="Compound lifts with progressive overload",
    ),
    _phase(
        role="metcon",
        target_adaptation="metabolic conditioning and work capacity",
        time_share=0.25,
        min_duration=10,
        priority=4,
        block_type="circuit",
        block_notes="Metabolic circuit with short rest",
    ),
    _phase(
        role="cooldown",
        target_adaptation="parasympathetic recovery and flexibility",
        time_share=0.10,
        min_duration=5,
        priority=5,
        block_type="steady_state",
        block_notes="Static stretching and breathing",
    ),
]

# ---- zone2: low-intensity aerobic ----
_ZONE2_TEMPLATE: list[Phase] = [
    _phase(
        role="mobility",
        target_adaptation="hip and thoracic mobility preparation",
        time_share=0.10,
        min_duration=5,
        priority=3,
        block_type="circuit",
        block_notes="Light dynamic mobility",
    ),
    _phase(
        role="strength",
        target_adaptation="aerobic base and fat oxidation",
        time_share=0.85,
        min_duration=20,
        priority=1,
        block_type="steady_state",
        block_notes="Sustained Zone-2 effort (HR 130-150 bpm, conversational pace)",
    ),
    _phase(
        role="cooldown",
        target_adaptation="heart rate recovery",
        time_share=0.05,
        min_duration=3,
        priority=5,
        block_type="steady_state",
        block_notes="Easy walk/spin cool-down",
    ),
]

# ---- hyrox_prep: HYROX race preparation ----
_HYROX_PREP_TEMPLATE: list[Phase] = [
    _phase(
        role="mobility",
        target_adaptation="hip flexor and thoracic spine mobility for running position",
        time_share=0.08,
        min_duration=4,
        priority=3,
        block_type="circuit",
        block_notes="Hip flexor stretch, world's greatest stretch, thoracic rotation",
    ),
    _phase(
        role="primer",
        target_adaptation="glute and posterior chain activation before heavy carry work",
        time_share=0.07,
        min_duration=3,
        priority=4,
        block_type="circuit",
        block_notes="Glute bridge, banded hip thrust, lateral band walk",
    ),
    _phase(
        role="strength",
        target_adaptation="functional strength for sled, carry, and row stations",
        time_share=0.30,
        min_duration=15,
        priority=1,
        block_type="strength",
        block_notes="Sled push/pull, sandbag clean, loaded carries",
    ),
    _phase(
        role="station_brick",
        target_adaptation="HYROX race simulation — run + functional station pairings",
        time_share=0.40,
        min_duration=15,
        priority=2,
        block_type="interval",
        block_notes=(
            "Run 200-400m + wall balls / SkiErg / burpee broad jump / farmers carry. "
            "Aim for race-pace efforts with 90s recovery between bricks."
        ),
    ),
    _phase(
        role="cooldown",
        target_adaptation="lactate clearance and joint mobility",
        time_share=0.15,
        min_duration=5,
        priority=5,
        block_type="steady_state",
        block_notes="Easy jog or walk, hip flexor and hamstring stretch",
    ),
]

# ---- tactical_circuit: functional fitness / military-style ----
_TACTICAL_CIRCUIT_TEMPLATE: list[Phase] = [
    _phase(
        role="mobility",
        target_adaptation="full-body movement preparation",
        time_share=0.10,
        min_duration=5,
        priority=3,
        block_type="circuit",
        block_notes="Bear crawl, world's greatest stretch, shoulder CARs",
    ),
    _phase(
        role="primer",
        target_adaptation="scapular stability and core bracing",
        time_share=0.10,
        min_duration=4,
        priority=4,
        block_type="circuit",
        block_notes="Dead bug, hollow body hold, banded pull-aparts",
    ),
    _phase(
        role="metcon",
        target_adaptation="functional work capacity and muscular endurance",
        time_share=0.65,
        min_duration=20,
        priority=1,
        block_type="amrap",
        block_notes="Tactical AMRAP: push-ups, kettlebell swings, sandbag carry, box jumps",
    ),
    _phase(
        role="cooldown",
        target_adaptation="recovery and parasympathetic activation",
        time_share=0.15,
        min_duration=5,
        priority=5,
        block_type="steady_state",
        block_notes="Static stretch and diaphragmatic breathing",
    ),
]

# Public registry
TEMPLATES: dict[str, list[Phase]] = {
    "default": _DEFAULT_TEMPLATE,
    "zone2": _ZONE2_TEMPLATE,
    "hyrox_prep": _HYROX_PREP_TEMPLATE,
    "tactical_circuit": _TACTICAL_CIRCUIT_TEMPLATE,
}


# ---------------------------------------------------------------------------
# Keyword→template mapping for prompt-based selection
# ---------------------------------------------------------------------------

_METHODOLOGY_KEYWORDS: dict[str, list[str]] = {
    "hyrox_prep": [
        "hyrox", "hyrox-style", "hyrox prep", "station brick", "station-brick",
        "race sim", "race simulation", "wall ball", "sled push", "sled pull",
        "ski erg", "skierg", "functional fitness race",
    ],
    "zone2": [
        "zone 2", "zone-2", "zone2", "z2", "aerobic base", "easy bike",
        "steady state", "steady-state", "low intensity", "fat oxidation",
        "conversational pace", "endurance",
    ],
    "tactical_circuit": [
        "tactical", "military", "functional fitness", "crossfit",
        "amrap", "emom", "wod", "work capacity", "circuit",
    ],
}


def select_template(
    prompt: str,
    methodology: str | None = None,
) -> list[Phase]:
    """
    Return a deep-copied template for the requested methodology.

    Selection priority:
      1. Explicit methodology key (e.g. "hyrox_prep") if provided and valid.
      2. Keyword scan of the prompt against _METHODOLOGY_KEYWORDS.
      3. Fallback: "default".

    Deep-copying ensures callers can mutate the returned list/phases without
    poisoning the canonical template definitions.

    Parameters
    ----------
    prompt:
        The coach's free-text prompt (e.g. "HYROX-style 45 min").
    methodology:
        Optional explicit methodology key.  If provided and recognised,
        skips keyword detection.

    Returns
    -------
    A deep-copied list[Phase] ready for time allocation.
    """
    # 1. Explicit key
    if methodology and methodology in TEMPLATES:
        return copy.deepcopy(TEMPLATES[methodology])

    # 2. Keyword scan (case-insensitive)
    lower_prompt = prompt.lower()
    for key, keywords in _METHODOLOGY_KEYWORDS.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", lower_prompt):
                return copy.deepcopy(TEMPLATES[key])

    # 3. Default
    return copy.deepcopy(TEMPLATES["default"])


# ---------------------------------------------------------------------------
# Time allocation
# ---------------------------------------------------------------------------


def allocate_time(
    template: list[Phase],
    total_minutes: int,
) -> list[Phase]:
    """
    Scale a template's phases to a concrete time budget.

    Algorithm
    ---------
    1. Compute each phase's raw allocation = time_share × total_minutes.
    2. Identify phases whose raw allocation < min_duration.
    3. Drop under-budget phases in ascending priority order (5 first, 1 last),
       stopping as soon as every remaining phase can meet its min_duration.
       Priority-1 phases are never dropped regardless of budget.
    4. Re-scale surviving phases so they sum to total_minutes.
    5. Update each phase's `allocated_minutes` and its first block's
       `duration_minutes`.

    Parameters
    ----------
    template:
        Deep-copied list[Phase] from select_template().
    total_minutes:
        The available session window in minutes.

    Returns
    -------
    A list[Phase] with allocated_minutes and block durations set.
    Phases that were dropped are excluded.

    Raises
    ------
    ValueError
        If total_minutes ≤ 0, or if no phases survive after dropping
        (should not happen because priority-1 phases are never dropped).
    """
    if total_minutes <= 0:
        raise ValueError(f"total_minutes must be > 0, got {total_minutes}")

    phases = list(template)  # shallow copy of the list; Phase objects are already copies

    # Sort priorities for drop order: highest priority number (least important) first
    # We'll iterate dropping until all remaining phases fit
    drop_priority_order = sorted(
        set(p.priority for p in phases if p.priority > 1),
        reverse=True,  # 5, 4, 3, 2 — 1 is never dropped
    )

    for drop_prio in drop_priority_order:
        # Check if every surviving phase can meet its min_duration
        surviving = [p for p in phases]
        raw = {p.role: p.time_share * total_minutes for p in surviving}

        under_budget = [p for p in surviving if raw[p.role] < p.min_duration]
        if not under_budget:
            break  # All phases fit — no more dropping needed

        # Drop all phases at this priority level that are under budget
        to_drop_roles = {p.role for p in under_budget if p.priority >= drop_prio}
        if to_drop_roles:
            phases = [p for p in phases if p.role not in to_drop_roles]

    # Re-normalise time_shares among surviving phases so they sum to 1.0
    total_share = sum(p.time_share for p in phases)
    if total_share <= 0:
        total_share = 1.0  # safety guard; should never happen

    allocated: list[Phase] = []
    for phase in phases:
        minutes = (phase.time_share / total_share) * total_minutes
        # Round to one decimal place for readability
        minutes = round(minutes, 1)
        phase.allocated_minutes = minutes

        # Update the first block's duration to match the phase allocation
        if phase.blocks:
            phase.blocks[0] = phase.blocks[0].model_copy(
                update={"duration_minutes": minutes}
            )

        allocated.append(phase)

    return allocated


def build_session_plan(
    prompt: str,
    total_minutes: int,
    methodology: str | None = None,
) -> SessionPlan:
    """
    Convenience wrapper: select template, allocate time, return a SessionPlan.

    Parameters
    ----------
    prompt:
        The coach's free-text prompt.
    total_minutes:
        The session time window.
    methodology:
        Optional explicit methodology key.

    Returns
    -------
    SessionPlan with allocated phases and metadata.
    """
    resolved_methodology = methodology or "default"
    # Detect from prompt if not explicitly provided
    if not methodology:
        template_phases = select_template(prompt)
        # Figure out which key was actually selected via keyword scan
        for key, keywords in _METHODOLOGY_KEYWORDS.items():
            lower_prompt = prompt.lower()
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", lower_prompt):
                    resolved_methodology = key
                    break
            if resolved_methodology != "default":
                break
    else:
        template_phases = select_template(prompt, methodology)

    if methodology:
        template_phases = select_template(prompt, methodology)

    allocated = allocate_time(template_phases, total_minutes)

    return SessionPlan(
        phases=allocated,
        total_minutes=total_minutes,
        methodology=resolved_methodology,
        prompt=prompt,
    )
