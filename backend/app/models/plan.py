"""
WorkoutPlan models — Phase 6 (updated with exercise sequencing fields).

Pydantic models for a structured workout plan returned by the generator
pipeline.  The plan has three sections (warmup / main / cooldown), each
containing PlannedExercise entries with sets, reps / duration, rest, a
per-exercise selection rationale, AND sequencing fields that explain WHY
the exercise sits at its specific position in the order.

Session-level fields (stimulus, target_adaptation, design_rationale,
sequence_logic) let the Copilot explain WHY the plan was designed the way
it was without having to re-examine raw exercise data.
"""

from __future__ import annotations

from typing import Literal

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
    rest_seconds: int = Field(default=60, ge=0)
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
