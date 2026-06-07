"""
Base deterministic safety filter.

This is a pure function — no LLM, no network, no randomness.  Given:
  - a candidate list of exercises
  - the joints that are currently injured
  - the equipment available to the member
  - explicit exercise ids to exclude
  - exercise name/pattern strings the member dislikes
  - a built MovementKG

…it returns a FilterTrace with:
  - safe          : exercises that passed all gates
  - removed       : (exercise, reason) pairs for every exclusion
  - substitutions : (dropped, substitute, rationale) triples where the filter
                    found a structurally equivalent safe replacement

Safety gates (applied in order):
  1. Injury gate   : excludes any exercise that stresses an injured joint
                     (determined via MovementKG.descendants_by_part_of + exercises_stressing)
  2. Equipment gate: excludes any exercise that requires gear not in the
                     member's available set
  3. Explicit gate : excludes exercises whose id is in excluded_ids
  4. Dislike gate  : excludes exercises whose name contains a disliked substring
                     (case-insensitive)

After exclusions, the filter attempts to find substitutions for dropped
exercises using a simple heuristic:
  - same primary movement pattern
  - same primary muscle group(s)
  - exercise passes all gates

Substitutions are best-effort — not every dropped exercise has a suitable
substitute in the catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.graph.movement_kg import MovementKG
from app.models.exercise import Exercise


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class FilterTrace:
    """
    Complete record of what the safety filter did.

    Attributes
    ----------
    safe:
        Exercises that passed every gate.
    removed:
        (exercise, reason_string) for every exercise that was excluded.
        reason_string is a human-readable explanation, e.g.
        "stresses injured joint: knee" or "requires unavailable equipment: Barbell".
    substitutions:
        (dropped_exercise, substitute_exercise, rationale) triples.
        The substitute is drawn from the safe pool.
    """

    safe: list[Exercise] = field(default_factory=list)
    removed: list[tuple[Exercise, str]] = field(default_factory=list)
    substitutions: list[tuple[Exercise, Exercise, str]] = field(default_factory=list)

    @property
    def safe_ids(self) -> set[str]:
        return {ex.id for ex in self.safe}

    @property
    def removed_ids(self) -> set[str]:
        return {ex.id for ex, _ in self.removed}


# ---------------------------------------------------------------------------
# Filter entry-point
# ---------------------------------------------------------------------------


def safety_filter(
    candidates: list[Exercise],
    injured_joints: list[str],
    available_equipment: set[str],
    excluded_ids: set[str],
    dislikes: set[str],
    kg: MovementKG,
) -> FilterTrace:
    """
    Apply the deterministic safety filter and return a FilterTrace.

    Parameters
    ----------
    candidates:
        The pool of exercises to evaluate (usually the full catalog or a
        subset pre-selected by pattern/muscle matching).
    injured_joints:
        List of joint catalog slugs that are currently injured, e.g. ["knee"].
        The filter expands each to its SNOMED descendants via part-of traversal.
    available_equipment:
        Set of equipment pref_labels or raw strings available to the member.
        Matching is case-insensitive.
    excluded_ids:
        Set of exercise ids to unconditionally exclude (e.g. coach overrides).
    dislikes:
        Set of dislike strings (e.g. {"Deadlift", "Burpees"}).  Any exercise
        whose name contains a dislike substring (case-insensitive) is excluded.
    kg:
        A built MovementKG instance.

    Returns
    -------
    FilterTrace
        Contains safe exercises, removal reasons, and attempted substitutions.
    """

    trace = FilterTrace()

    # 1. Expand injured joints to all SNOMED-descendant node ids
    injured_node_ids: set[str] = set()
    for joint_slug in injured_joints:
        injured_node_ids.update(kg.descendants_by_part_of(joint_slug))

    # 2. Determine exercises that stress injured joints
    stressing_ids: set[str] = kg.exercises_stressing(injured_node_ids) if injured_node_ids else set()

    # 3. Normalise available equipment for case-insensitive lookup
    available_norm: set[str] = {e.lower().strip() for e in available_equipment}

    # 4. Normalise dislikes
    dislikes_norm: set[str] = {d.lower().strip() for d in dislikes}

    # 5. Apply gates (evaluated in priority order; first match wins)
    for ex in candidates:
        removal_reason: str | None = None

        # Gate 1: Injury — highest priority
        if removal_reason is None and ex.id in stressing_ids:
            joints_hit = _joints_stressed_in_injured_set(ex, injured_node_ids, kg)
            removal_reason = f"stresses injured joint: {', '.join(joints_hit)}"

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

    # 6. Attempt substitutions for each removed exercise
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _joints_stressed_in_injured_set(
    ex: Exercise, injured_node_ids: set[str], kg: MovementKG
) -> list[str]:
    """
    Return a human-readable list of injured joint labels that this exercise stresses.
    """
    hit: list[str] = []
    g = kg.graph
    if not g.has_node(ex.id):
        return hit
    for _, target, data in g.out_edges(ex.id, data=True):
        if data.get("relation") == "stresses" and target in injured_node_ids:
            # Prefer the pref_label stored on the node
            label = g.nodes[target].get("pref_label", target)
            hit.append(label)
    return hit


def _matches_dislikes(exercise_name: str, dislikes_norm: set[str]) -> bool:
    """Return True if the exercise name contains any disliked substring."""
    name_lower = exercise_name.lower()
    return any(dislike in name_lower for dislike in dislikes_norm)


def _find_substitute(
    dropped: Exercise, safe_pool: list[Exercise]
) -> Exercise | None:
    """
    Find a substitute from safe_pool with the same primary movement pattern
    and overlapping muscle groups.

    Returns None if no suitable substitute is found.
    """
    if not dropped.movement_patterns or not safe_pool:
        return None

    primary_pattern = dropped.movement_patterns[0]
    dropped_muscles = set(dropped.muscle_groups)

    best: Exercise | None = None
    best_overlap = 0

    for candidate in safe_pool:
        if primary_pattern not in candidate.movement_patterns:
            continue
        overlap = len(set(candidate.muscle_groups) & dropped_muscles)
        if overlap > best_overlap:
            best_overlap = overlap
            best = candidate

    return best
