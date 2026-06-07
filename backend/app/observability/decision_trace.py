"""
In-app decision trace — Phase 7.

Exposes the deterministic graph decisions (safety filter / part-of traversal)
as an inspectable ordered list of steps so the frontend (Phase 9/10) can
render a "how did we get here" panel for each generated plan.

Public API
----------

DecisionStep
    Typed dataclass for a single step in the decision pipeline:
      name, detail, inputs, outputs, kind ("deterministic" | "llm")

build_decision_trace(...)
    Constructs the ordered step list from a ConditionalFilterTrace + the
    generator's prompt / member / injury context.  Steps:
      1. resolve_prompt         — deterministic: concept extraction from prompt
      2. load_constraints       — deterministic: member equipment + dislikes
      3. part_of_traversal      — deterministic: SNOMED anatomy traversal for
                                  the injured joint
      4. movement_type_exclusion — deterministic: exclude exercises by pain_on
                                   movement types at the injured joint
      5. equipment_gate         — deterministic: equipment availability filter
      6. llm_structuring        — llm: LLM turns safe set into WorkoutPlan (×3)

    When LangSmith is enabled, the llm_structuring step includes a
    "langsmith_url" key in its outputs dict with the run URL template.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal


# ---------------------------------------------------------------------------
# DecisionStep
# ---------------------------------------------------------------------------


@dataclass
class DecisionStep:
    """
    A single step in the workout-generation decision pipeline.

    Attributes
    ----------
    name:
        Machine-readable step identifier (e.g. "part_of_traversal").
    detail:
        Human-readable sentence describing what this step does.
    inputs:
        Dict of input values / parameters for this step.
    outputs:
        Dict of output values / results from this step.
    kind:
        "deterministic" — pure function, no LLM, fully reproducible.
        "llm"           — calls a language model; output may vary.
    duration_ms:
        Wall-clock time spent in this phase, in milliseconds. None when the
        phase was not individually timed (e.g. sub-millisecond bookkeeping
        steps). Rendered very small in the expanded decision-trace view.
    """

    name: str
    detail: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    kind: Literal["deterministic", "llm"] = "deterministic"
    duration_ms: float | None = None


# ---------------------------------------------------------------------------
# build_decision_trace
# ---------------------------------------------------------------------------


def build_decision_trace(
    *,
    prompt: str,
    member_id: str,
    injury_joint: str | None,
    injured_node_ids: set[str] | None,
    excluded_movement_types: set[str] | None,
    available_equipment: set[str],
    dislikes: set[str],
    safe_count: int,
    removed_count: int,
    removed_exercises: list[dict],  # [{"name": ..., "reason": ...}]
    variant_ids: list[str],
    langsmith_run_url: str | None = None,
    timings: dict[str, float] | None = None,
) -> list[DecisionStep]:
    """
    Build the ordered decision trace for one generator pipeline run.

    Parameters
    ----------
    prompt:
        The coach's original free-text prompt.
    member_id:
        The member the plan was generated for.
    injury_joint:
        The injured joint's catalog slug (e.g. "knee", "lumbar_spine"),
        or None if the member has no injury.
    injured_node_ids:
        Set of SNOMED descendant node ids returned by
        kg.descendants_by_part_of(injury_joint).  None if no injury.
    excluded_movement_types:
        Set of movement types excluded by phase + pain_on logic.
        None if no injury.
    available_equipment:
        The member's available equipment set.
    dislikes:
        The member's dislike terms.
    safe_count:
        Number of exercises that passed all filters.
    removed_count:
        Number of exercises removed by any gate.
    removed_exercises:
        List of dicts {"name": ..., "id": ..., "reason": ...} for each
        removed exercise (from the ConditionalFilterTrace).
    variant_ids:
        The variant ids that were structured (e.g. ["strength", "conditioning",
        "mobility"]).
    langsmith_run_url:
        Optional LangSmith run URL to attach to the llm_structuring step.
        When LangSmith is enabled (see tracing.py) the caller can pass
        the project URL for deep-linking.

    Returns
    -------
    list[DecisionStep]
        Ordered steps from prompt resolution through LLM structuring.
    """
    steps: list[DecisionStep] = []

    # ------------------------------------------------------------------
    # Step 1 — Resolve prompt concepts
    # ------------------------------------------------------------------
    steps.append(
        DecisionStep(
            name="resolve_prompt",
            detail=(
                "Extract concept terms from the coach's free-text prompt using "
                "the 3-pass resolver (exact → fuzzy → embedding)."
            ),
            inputs={"prompt": prompt},
            outputs={"member_id": member_id},
            kind="deterministic",
        )
    )

    # ------------------------------------------------------------------
    # Step 2 — Load member constraints
    # ------------------------------------------------------------------
    steps.append(
        DecisionStep(
            name="load_constraints",
            detail="Load member equipment list and dislikes for downstream gates.",
            inputs={"member_id": member_id},
            outputs={
                "equipment_count": len(available_equipment),
                "equipment_sample": sorted(available_equipment)[:5],
                "dislikes": sorted(dislikes),
                "injury_joint": injury_joint or "none",
            },
            kind="deterministic",
        )
    )

    # ------------------------------------------------------------------
    # Step 3 — Part-of traversal (only when injury present)
    # ------------------------------------------------------------------
    if injury_joint is not None:
        steps.append(
            DecisionStep(
                name="part_of_traversal",
                detail=(
                    f"Traverse the SNOMED anatomy part-of hierarchy from "
                    f"'{injury_joint}' to collect all descendant anatomical nodes "
                    f"(e.g. patellofemoral joint, tibial plateau) that are "
                    f"part of the injured region.  Exercises stressing any of "
                    f"these nodes are candidates for exclusion."
                ),
                inputs={"injured_joint": injury_joint},
                outputs={
                    "descendant_node_count": (
                        len(injured_node_ids) if injured_node_ids else 0
                    ),
                    "descendant_nodes": sorted(
                        injured_node_ids or set()
                    )[:10],  # sample — may be many SNOMED codes
                },
                kind="deterministic",
            )
        )
    else:
        steps.append(
            DecisionStep(
                name="part_of_traversal",
                detail="No injury reported — part-of traversal skipped.",
                inputs={"injured_joint": "none"},
                outputs={"descendant_node_count": 0},
                kind="deterministic",
            )
        )

    # ------------------------------------------------------------------
    # Step 4 — Movement-type exclusion
    # ------------------------------------------------------------------
    if injury_joint is not None and excluded_movement_types is not None:
        detail = (
            f"Exclude exercises that perform any of {sorted(excluded_movement_types)} "
            f"at the injured joint '{injury_joint}' based on today's pain_on check-in "
            f"and the active healing phase's movement restrictions."
        )
        if not excluded_movement_types:
            detail = (
                f"No movement types excluded at joint '{injury_joint}' — "
                "today's check-in reported no pain triggers and the healing "
                "phase has no movement-type restrictions."
            )
    else:
        detail = "No injury — movement-type exclusion gate skipped."

    steps.append(
        DecisionStep(
            name="movement_type_exclusion",
            detail=detail,
            inputs={
                "injured_joint": injury_joint or "none",
                "excluded_movement_types": (
                    sorted(excluded_movement_types)
                    if excluded_movement_types
                    else []
                ),
            },
            outputs={
                "exercises_removed_by_injury": sum(
                    1
                    for r in removed_exercises
                    if "movement type" in r.get("reason", "")
                    or "stresses injured" in r.get("reason", "")
                ),
            },
            kind="deterministic",
        )
    )

    # ------------------------------------------------------------------
    # Step 5 — Equipment gate
    # ------------------------------------------------------------------
    equipment_removals = [
        r for r in removed_exercises
        if "equipment" in r.get("reason", "").lower()
    ]
    steps.append(
        DecisionStep(
            name="equipment_gate",
            detail=(
                "Remove exercises that require equipment the member does not have."
            ),
            inputs={
                "available_equipment_count": len(available_equipment),
            },
            outputs={
                "exercises_removed_by_equipment": len(equipment_removals),
                "removed_examples": [r["name"] for r in equipment_removals[:3]],
            },
            kind="deterministic",
        )
    )

    # ------------------------------------------------------------------
    # Step 6 — LLM structuring
    # ------------------------------------------------------------------
    llm_outputs: dict[str, Any] = {
        "safe_exercise_count": safe_count,
        "total_removed": removed_count,
        "variants_structured": variant_ids,
    }
    if langsmith_run_url:
        llm_outputs["langsmith_url"] = langsmith_run_url
    elif _langsmith_enabled():
        # Tracing is on but we don't have the specific run URL yet —
        # include the project dashboard URL as a fallback
        project = os.environ.get("LANGCHAIN_PROJECT", "").strip()
        if project:
            llm_outputs["langsmith_project"] = project

    steps.append(
        DecisionStep(
            name="llm_structuring",
            detail=(
                f"The LLM receives only the {safe_count} safe exercises and "
                "structures them into a single WorkoutPlan — assigning sets, "
                "reps, rest, per-exercise rationale, sequencing roles, the "
                "session-level stimulus/target_adaptation/design_rationale, and "
                "the strength/conditioning/mobility stimulus distribution."
            ),
            inputs={
                "safe_exercise_count": safe_count,
                "variants": variant_ids,
            },
            outputs=llm_outputs,
            kind="llm",
        )
    )

    # Apply per-phase wall-clock timings where available (keyed by step name).
    if timings:
        for step in steps:
            if step.name in timings:
                step.duration_ms = round(timings[step.name], 1)

    return steps


def _langsmith_enabled() -> bool:
    """Local helper to avoid circular import with tracing.py."""
    tracing = os.environ.get("LANGCHAIN_TRACING_V2", "").strip().lower()
    api_key = os.environ.get("LANGCHAIN_API_KEY", "").strip()
    return tracing == "true" and bool(api_key)
