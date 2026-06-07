"""
Conditional Safety Filter — Phase 5.

Extends the base safety_filter with dynamic, state-aware filtering based on
today's injury check-in.  The filter logic:

  1. Get today's InjuryState (most recent check-in, with staleness warning)
  2. Determine the current healing phase (computed or coach-overridden)
  3. Apply phase-level movement type restrictions (acute = strict, RTA = permissive)
  4. Exclude exercises matching pain_on movement types at the injured joint
  5. Record load_tolerance_pct as an intensity cap (not a filter gate, but
     propagated in the trace for the generator to honour)
  6. Fall through to base filter for equipment / dislikes / explicit excludes

This is a pure function — no LLM, no network, no side effects.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from app.graph.movement_kg import MovementKG
from app.graph.safety_filter import FilterTrace, _find_substitute, _matches_dislikes
from app.models.exercise import Exercise
from app.models.healing import PHASE_RESTRICTIONS
from app.models.injury import HealingPhase, Injury, InjuryState


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ConditionalFilterTrace(FilterTrace):
    """
    Extends FilterTrace with injury-state and phase metadata.

    Attributes
    ----------
    injury_state_used:
        The InjuryState that drove the movement-type exclusions.
        None if the injury has no check-ins (falls back to phase-only rules).
    phase_restrictions_applied:
        The PHASE_RESTRICTIONS dict entry for the active phase.
    load_tolerance_pct:
        The effective load tolerance cap for this session (0.0-1.0).
        Derived from: min(today_state.load_tolerance_pct, phase_max_load_tolerance).
        The generator uses this to cap planned intensity percentages.
    stale_check_in:
        True if the most recent state is not from today (may be outdated).
    """

    injury_state_used: InjuryState | None = None
    phase_restrictions_applied: dict = field(default_factory=dict)
    load_tolerance_pct: float = 1.0
    stale_check_in: bool = False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def conditional_safety_filter(
    candidates: list[Exercise],
    injury: Injury,
    available_equipment: set[str],
    excluded_ids: set[str],
    dislikes: set[str],
    kg: MovementKG,
    reference_date: date | None = None,
) -> ConditionalFilterTrace:
    """
    Apply the dynamic, injury-state-aware safety filter.

    Parameters
    ----------
    candidates:
        Pool of exercises to evaluate.
    injury:
        The full Injury record (with states time series).
    available_equipment:
        Set of equipment identifiers available to the member.
    excluded_ids:
        Exercise ids to unconditionally exclude.
    dislikes:
        Dislike substrings (case-insensitive name matching).
    kg:
        A built MovementKG instance.
    reference_date:
        The "today" date.  Defaults to date.today() if not provided.
        Inject a fixed date in tests for determinism.

    Returns
    -------
    ConditionalFilterTrace
    """
    ref_date = reference_date or date.today()

    # ------------------------------------------------------------------
    # 1. Determine active healing phase
    # ------------------------------------------------------------------
    active_phase: HealingPhase = injury.computed_phase(ref_date)
    phase_restrictions: dict = PHASE_RESTRICTIONS[active_phase]

    # ------------------------------------------------------------------
    # 2. Resolve today's injury state
    # ------------------------------------------------------------------
    today_state: InjuryState | None = None
    stale = False

    current = injury.current_state()
    if current is not None:
        if current.recorded_at.date() == ref_date:
            today_state = current
        else:
            # Most recent state is not from today — use it with a staleness flag
            today_state = current
            stale = True
            warnings.warn(
                f"No check-in today ({ref_date}) for injury '{injury.id}'. "
                f"Using most recent state from {current.recorded_at.date()}.",
                UserWarning,
                stacklevel=2,
            )

    # ------------------------------------------------------------------
    # 3. Build the set of movement types to exclude at the injured joint
    # ------------------------------------------------------------------
    # Start with phase-level exclusions (minimum safety floor)
    excluded_movement_types: set[str] = set(
        phase_restrictions.get("excluded_movement_types", [])
    )

    # Layer in pain_on exclusions from today's state
    if today_state is not None:
        for pain_type in today_state.pain_on:
            excluded_movement_types.add(pain_type)

    # ------------------------------------------------------------------
    # 4. Determine load tolerance cap
    # ------------------------------------------------------------------
    phase_max_load = phase_restrictions.get("max_load_tolerance", 1.0)
    if today_state is not None:
        state_tol = today_state.load_tolerance_pct
        effective_load_tol = min(state_tol, phase_max_load)
    else:
        effective_load_tol = phase_max_load

    # ------------------------------------------------------------------
    # 5. Expand injured joint to SNOMED descendants
    # ------------------------------------------------------------------
    injured_node_ids: set[str] = kg.descendants_by_part_of(injury.joint)

    # ------------------------------------------------------------------
    # 6. Build dynamic exclusion set:
    #    exercises that perform an excluded movement type at the injured joint
    # ------------------------------------------------------------------
    dynamic_excluded_ids: set[str] = set()
    dynamic_reason: dict[str, str] = {}  # exercise_id -> human-readable reason

    for ex in candidates:
        if not kg.graph.has_node(ex.id):
            continue

        for _, target, edge_data in kg.graph.out_edges(ex.id, data=True):
            if edge_data.get("relation") != "stresses":
                continue
            if target not in injured_node_ids:
                continue

            # This exercise stresses the injured joint — check movement types
            ex_movement_types: list[str] = edge_data.get("movement_types", [])
            matched_exclusions = set(ex_movement_types) & excluded_movement_types

            if matched_exclusions:
                dynamic_excluded_ids.add(ex.id)
                joint_label = kg.graph.nodes[target].get("pref_label", target)
                dynamic_reason[ex.id] = (
                    f"movement type(s) {sorted(matched_exclusions)} excluded "
                    f"at injured joint '{joint_label}' "
                    f"(phase: {active_phase.value}"
                    + (
                        f"; pain on: {sorted(today_state.pain_on)}"
                        if today_state and today_state.pain_on
                        else ""
                    )
                    + ")"
                )
                break  # one matching edge is enough to exclude

    # ------------------------------------------------------------------
    # 7. Also exclude exercises that stress the injured joint at all
    #    (joint-level exclusion regardless of movement type) only when
    #    acute phase or the injury has no movement-type annotations.
    # ------------------------------------------------------------------
    # For exercises stressing the injured joint that have NO movement-type
    # annotations, fall back to the base joint-level exclusion.
    joint_stressing_ids: set[str] = kg.exercises_stressing(injured_node_ids)

    unannotated_joint_exclusions: set[str] = set()
    unannotated_reason: dict[str, str] = {}

    for ex_id in joint_stressing_ids:
        ex_node_data = kg.graph.nodes.get(ex_id, {})
        if ex_id in dynamic_excluded_ids:
            continue  # already handled by movement-type logic

        # Check if this exercise has ANY movement-type annotations at the injured joint
        has_annotations = False
        if kg.graph.has_node(ex_id):
            for _, target, edge_data in kg.graph.out_edges(ex_id, data=True):
                if (
                    edge_data.get("relation") == "stresses"
                    and target in injured_node_ids
                    and edge_data.get("movement_types")
                ):
                    has_annotations = True
                    break

        if not has_annotations:
            # No annotations → conservative: exclude if the joint is injured
            unannotated_joint_exclusions.add(ex_id)
            ex_obj = kg.get_exercise(ex_id)
            label = ex_obj.name if ex_obj else ex_id
            unannotated_reason[ex_id] = (
                f"stresses injured joint '{injury.joint}' "
                f"(no movement-type annotation; conservative exclusion)"
            )

    # ------------------------------------------------------------------
    # 8. Normalise available equipment and dislikes for matching
    # ------------------------------------------------------------------
    available_norm: set[str] = {e.lower().strip() for e in available_equipment}
    dislikes_norm: set[str] = {d.lower().strip() for d in dislikes}

    # ------------------------------------------------------------------
    # 9. Apply all gates in priority order
    # ------------------------------------------------------------------
    trace = ConditionalFilterTrace(
        injury_state_used=today_state,
        phase_restrictions_applied=phase_restrictions,
        load_tolerance_pct=effective_load_tol,
        stale_check_in=stale,
    )

    for ex in candidates:
        removal_reason: str | None = None

        # Gate 1a: Dynamic movement-type exclusion at injured joint
        if removal_reason is None and ex.id in dynamic_excluded_ids:
            removal_reason = dynamic_reason[ex.id]

        # Gate 1b: Unannotated joint-stressing exclusion
        if removal_reason is None and ex.id in unannotated_joint_exclusions:
            removal_reason = unannotated_reason[ex.id]

        # Gate 2: Equipment
        if removal_reason is None and ex.equipment_required:
            missing = [
                eq for eq in ex.equipment_required
                if eq.lower().strip() not in available_norm
            ]
            if missing:
                removal_reason = f"requires unavailable equipment: {', '.join(missing)}"

        # Gate 3: Explicit excludes
        if removal_reason is None and ex.id in excluded_ids:
            removal_reason = "explicitly excluded"

        # Gate 4: Dislikes
        if removal_reason is None and _matches_dislikes(ex.name, dislikes_norm):
            removal_reason = f"member dislike: {ex.name}"

        if removal_reason:
            trace.removed.append((ex, removal_reason))
        else:
            trace.safe.append(ex)

    # ------------------------------------------------------------------
    # 10. Attempt substitutions for each removed exercise
    # ------------------------------------------------------------------
    for dropped_ex, reason in trace.removed:
        substitute = _find_substitute(dropped_ex, trace.safe)
        if substitute:
            rationale = (
                f"Substituted '{substitute.name}' for '{dropped_ex.name}': "
                f"same pattern ({', '.join(dropped_ex.movement_patterns[:1])}); "
                f"reason for drop: {reason}"
            )
            trace.substitutions.append((dropped_ex, substitute, rationale))

    return trace
