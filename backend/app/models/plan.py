"""
WorkoutPlan models — Phase 6 (updated with exercise sequencing fields).
Phase 11: Extended with Block, Phase, and SessionPlan for advanced formats
(HYROX, Zone-2, tactical circuits).

Pydantic models for a structured workout plan returned by the generator
pipeline.  The plan has three sections (warmup / main / cooldown), each
containing PlannedExercise entries with sets, reps / duration, rest, a
per-exercise selection rationale, AND sequencing fields that explain WHY
the exercise sits at its specific position in the order.

Session-level fields (stimulus, target_adaptation, design_rationale,
sequence_logic) let the Copilot explain WHY the plan was designed the way
it was without having to re-examine raw exercise data.

Phase 11 additions (additive — do NOT break Phase 6/9 WorkoutPlan):
  - Block: a typed conditioning or strength block within a phase
    (strength / interval / amrap / emom / circuit / steady_state)
  - Phase: a named session phase with role, time budget, and ordered blocks
    (role: mobility / primer / strength / metcon / accessory / cooldown /
    station_brick)
  - SessionPlan: advanced session container (phases + total_minutes)
    used by HYROX-prep and Zone-2 templates; WorkoutPlan remains the
    primary output for the existing 3-variant generator.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PlannedExercise(BaseModel):
    """
    A single exercise slot in a structured plan section.

    Attributes
    ----------
    exercise_id:
        The catalog id of the exercise.
    name:
        Human-readable name (denormalised for display).
    order:
        1-based position within its section (warmup / main / cooldown).
        Must be unique and consecutive within a section.
    sets:
        Number of sets to perform.
    reps:
        Number of repetitions per set.  None for duration-based exercises.
    duration_seconds:
        Duration per set in seconds.  None for rep-based exercises.
    rest_seconds:
        Rest period between sets in seconds.
    rationale:
        One-sentence explanation of why this exercise was *chosen* and how
        it serves the session's intent (selection rationale, written by the
        structuring LLM).
    sequencing_rationale:
        One-to-two-sentence explanation of why this exercise sits HERE in
        the order — i.e. why it comes before/after its neighbours.
        e.g. "Placed before the squat: banded hip thrusts pre-activate the
        glutes so they fire correctly under load, sparing the lumbar spine."
    sequencing_role:
        Functional role that explains this exercise's placement in the
        session arc:
          - "activation"   — mobility / neuromuscular wake-up (typically early)
          - "primer"       — injury-protective pre-activation (e.g. glute
                             bridge before squat to protect knee/lumbar)
          - "compound"     — CNS-intensive multi-joint strength movement
          - "accessory"    — single-joint or isolation work after compounds
          - "conditioning" — metabolic / density work (after strength)
          - "cooldown"     — stretching / parasympathetic down-regulation
    """

    exercise_id: str
    name: str
    order: int = Field(default=1, ge=1, description="1-based position within its section")
    sets: int = Field(ge=1)
    reps: int | None = Field(default=None, ge=1)
    duration_seconds: int | None = Field(default=None, ge=1)
    # Cardio-machine / locomotion work is prescribed by distance or calories,
    # never by reps. Exactly one work metric (reps | duration_seconds |
    # distance_meters | calories) is set per exercise.
    distance_meters: int | None = Field(
        default=None, ge=1,
        description="Distance per set for locomotion/erg work (e.g. row, run, sled). None unless distance-based.",
    )
    calories: int | None = Field(
        default=None, ge=1,
        description="Calories per set for erg/machine conditioning (e.g. rower, SkiErg, assault bike). None unless calorie-based.",
    )
    rest_seconds: int = Field(default=60, ge=0)
    intensity_pct: int | None = Field(
        default=None, ge=1, le=100,
        description=(
            "Target intensity/effort as a percent — effort % for cardio/erg "
            "intervals (e.g. 85), ~65 for Zone-2 steady-state. None when not "
            "applicable (e.g. mobility)."
        ),
    )
    rationale: str = ""
    sequencing_rationale: str = Field(
        default="",
        description=(
            "Why this exercise sits HERE in the order — its relationship to "
            "the exercises immediately before and after it."
        ),
    )
    sequencing_role: Literal[
        "activation", "primer", "compound", "accessory", "conditioning", "cooldown"
    ] = Field(
        default="compound",
        description="Functional role that explains the exercise's placement.",
    )


class StimulusDistribution(BaseModel):
    """
    How strongly the generated session leans toward each training stimulus.

    Each value is an integer 0-100 representing the session's emphasis on that
    modality. The three need not sum to 100 — they are independent "thermometer"
    readings rendered as gauges in the UI so the coach can see at a glance how
    the single generated workout is catered across stimuli.
    """

    strength: int = Field(default=0, ge=0, le=100, description="Strength & hypertrophy emphasis")
    conditioning: int = Field(default=0, ge=0, le=100, description="Conditioning & metabolic emphasis")
    mobility: int = Field(default=0, ge=0, le=100, description="Mobility & recovery emphasis")


class WorkoutPlan(BaseModel):
    """
    A complete structured workout plan.

    Sections
    --------
    warmup:   Mobility / activation exercises (5-10 min)
    main:     Primary training block (bulk of session)
    cooldown: Cool-down / stretch exercises (5 min)

    Session-level "why" fields
    --------------------------
    stimulus:
        Primary training stimulus in plain language,
        e.g. "lower-body strength + knee-safe loading".
    target_adaptation:
        The physiological adaptation targeted by this session,
        e.g. "quad and glute hypertrophy under 70% load tolerance cap".
    design_rationale:
        How the prompt, injury state, and time window shaped the overall
        design — a paragraph that the Copilot can cite when answering
        "why was this workout designed this way?".
    sequence_logic:
        One-paragraph narrative of the overall ordering strategy for the
        session — e.g. explaining why activation comes first, why compounds
        precede accessories, and how the member's injury shaped the sequence.
        Answers the coach question "why are exercises in this order?".
    total_minutes:
        Estimated total session duration in minutes.
    """

    warmup: list[PlannedExercise] = Field(default_factory=list)
    main: list[PlannedExercise] = Field(default_factory=list)
    cooldown: list[PlannedExercise] = Field(default_factory=list)
    total_minutes: int = Field(ge=1)
    stimulus_distribution: StimulusDistribution = Field(
        default_factory=StimulusDistribution,
        description=(
            "Independent 0-100 emphasis readings for strength / conditioning / "
            "mobility, rendered as thermometer gauges so the coach sees how the "
            "session is catered across stimuli."
        ),
    )
    stimulus: str = ""
    target_adaptation: str = ""
    design_rationale: str = ""
    sequence_logic: str = Field(
        default="",
        description=(
            "One-paragraph narrative of the overall ordering strategy: "
            "why exercises appear in this sequence, referencing the member's "
            "injury where relevant (e.g. glute activation before squats to "
            "protect the lumbar spine)."
        ),
    )


# ---------------------------------------------------------------------------
# Phase 11 — Advanced format models (Block, Phase, SessionPlan)
#
# These are ADDITIVE to WorkoutPlan and do not affect the existing 3-variant
# generator pipeline.  They are used by the template-driven generator path
# (select_template / allocate_time in app/generator/templates.py).
# ---------------------------------------------------------------------------


BlockType = Literal["strength", "interval", "amrap", "emom", "circuit", "steady_state"]
PhaseRole = Literal[
    "mobility", "primer", "strength", "metcon", "accessory", "cooldown", "station_brick"
]


class Block(BaseModel):
    """
    A typed conditioning or strength block within a Phase.

    type:
        The format/modality of this block:
          - "strength"     — traditional sets × reps with rest periods
          - "interval"     — timed work:rest intervals (e.g. 40s on / 20s off)
          - "amrap"        — as-many-rounds-as-possible in a fixed window
          - "emom"         — every-minute-on-the-minute
          - "circuit"      — sequential exercises with minimal rest
          - "steady_state" — sustained aerobic effort (Zone-2, easy rowing)
    duration_minutes:
        Target block duration in minutes.
    exercise_ids:
        Ordered list of exercise ids included in this block.
    work_seconds:
        Work interval duration (used for interval / emom / circuit blocks).
        None for strength or steady_state blocks.
    rest_seconds:
        Rest interval between exercises or rounds.
        For steady_state this is typically 0.
    rounds:
        Number of rounds (used for amrap / emom / circuit).  None for
        strength or steady_state blocks.
    notes:
        Free-text coaching notes for this block (e.g. "target HR 130-150 bpm").
    extra:
        Flexible dict for type-specific fields not covered above
        (e.g. {"target_distance_m": 1000} for a rowing block).
    """

    type: BlockType
    duration_minutes: float = Field(ge=0.0)
    exercise_ids: list[str] = Field(default_factory=list)
    work_seconds: int | None = Field(default=None, ge=1)
    rest_seconds: int = Field(default=60, ge=0)
    rounds: int | None = Field(default=None, ge=1)
    notes: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class Phase(BaseModel):
    """
    A named segment of a training session containing one or more Blocks.

    role:
        The functional role of this phase within the session arc:
          - "mobility"       — dynamic warm-up, CARs, joint prep
          - "primer"         — injury-protective activation before compounds
          - "strength"       — primary strength/hypertrophy block
          - "metcon"         — metabolic conditioning (AMRAP, intervals, etc.)
          - "accessory"      — isolation or corrective work after compounds
          - "cooldown"       — parasympathetic down-regulation, static stretching
          - "station_brick"  — HYROX-style run + functional station pairing
    target_adaptation:
        One-line physiological adaptation targeted (e.g. "aerobic base",
        "lower-body power", "thoracic mobility").
    time_share:
        Proportional share of total session time (0.0-1.0).
        allocate_time() uses this to compute actual minute budgets.
    min_duration:
        Minimum viable duration in minutes.  If the scaled duration falls
        below this, the phase is dropped when time is constrained
        (unless priority == 1).
    priority:
        Drop order when time is constrained: lower value = drop first.
        Priority 1 (highest) phases are never dropped.
        Priority 5 (lowest) phases are dropped first.
    blocks:
        Ordered list of Block objects within this phase.
    """

    role: PhaseRole
    target_adaptation: str = ""
    time_share: float = Field(default=0.25, ge=0.0, le=1.0)
    min_duration: int = Field(default=5, ge=1, description="Minimum duration in minutes")
    priority: int = Field(default=3, ge=1, le=5, description="1=never drop, 5=drop first")
    blocks: list[Block] = Field(default_factory=list)
    # Computed at allocation time (not part of the template definition)
    allocated_minutes: float = Field(default=0.0, ge=0.0)


class SessionPlan(BaseModel):
    """
    Advanced session container used by the template-driven generator path.

    Unlike WorkoutPlan (which has warmup/main/cooldown sections), SessionPlan
    uses an ordered list of Phase objects — each with a role, time budget, and
    typed Block sub-structure.  This supports:
      - HYROX-prep sessions (station_brick + strength + metcon phases)
      - Zone-2 sessions (single steady_state phase)
      - Tactical circuits (primer + circuit + cooldown)

    WorkoutPlan remains the primary output for the existing 3-variant generator
    (Phases 6/9); SessionPlan is generated in parallel via templates.py and
    may be attached to a WorkoutVariant as an optional field in the future.

    Attributes
    ----------
    phases:
        Ordered list of phases after time allocation.  Phases that were
        dropped due to time constraints are excluded.
    total_minutes:
        The total session duration target used during allocation.
    methodology:
        The template/methodology key used (e.g. "hyrox_prep", "zone2").
    prompt:
        The original coach prompt that triggered this session.
    """

    phases: list[Phase] = Field(default_factory=list)
    total_minutes: int = Field(ge=1)
    methodology: str = ""
    prompt: str = ""
