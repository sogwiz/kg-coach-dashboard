"""
WorkoutPlan models — Phase 6.

Pydantic models for a structured workout plan returned by the generator
pipeline.  The plan has three sections (warmup / main / cooldown), each
containing PlannedExercise entries with sets, reps / duration, rest, and
a per-exercise rationale string.

Session-level fields (stimulus, target_adaptation, design_rationale) let the
Copilot explain WHY the plan was designed the way it was without having to
re-examine raw exercise data.
"""

from __future__ import annotations

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
    sets:
        Number of sets to perform.
    reps:
        Number of repetitions per set.  None for duration-based exercises.
    duration_seconds:
        Duration per set in seconds.  None for rep-based exercises.
    rest_seconds:
        Rest period between sets in seconds.
    rationale:
        One-sentence explanation of why this exercise was chosen and how
        it serves the session's intent (written by the structuring LLM).
    """

    exercise_id: str
    name: str
    sets: int = Field(ge=1)
    reps: int | None = Field(default=None, ge=1)
    duration_seconds: int | None = Field(default=None, ge=1)
    rest_seconds: int = Field(default=60, ge=0)
    rationale: str = ""


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
