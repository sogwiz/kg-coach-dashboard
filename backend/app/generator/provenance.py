"""
PROV-O Provenance Builder — Phase 12.

Produces a PROV-O-shaped JSON document for each generated workout variant,
enabling full traceability from the coach's prompt through to every exercise
in the plan.

PROV-O terms used:
  prov:Activity      — the plan-generation run itself
  prov:Agent         — the system (kg-coach-dashboard) that produced the plan
  prov:Entity        — each exercise in the plan
  prov:wasAssociatedWith — Activity ↔ Agent
  prov:used          — Activity used the InjuryState + FilterTrace as inputs
  prov:wasDerivedFrom — each planned exercise was derived from a safe candidate
  prov:startedAtTime / prov:endedAtTime — timing of the generation run

Reference: https://www.w3.org/TR/prov-o/

Design notes:
  - This builder is ADDITIVE to the existing GeneratorOutput / variants[]
    contract. It produces a Provenance object that is attached as the
    `provenance` field on WorkoutVariant (already present from Phase 6).
  - The Phase 6 Provenance dataclass carries a subset of these fields in a
    flatter shape. Phase 12 introduces build_provenance() which returns a
    PROV-O-shaped dict (suitable for serialisation to JSON or JSON-LD) that
    the frontend ProvenanceTrace panel can render.
  - filtered_out entries carry: exercise name/id, reason (human-readable),
    graph_path (the traversal that justified the exclusion), and
    injury_constraint (the specific pain_on or phase rule that fired).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.graph.conditional_filter import ConditionalFilterTrace
from app.models.injury import InjuryState
from app.models.plan import WorkoutPlan

# ---------------------------------------------------------------------------
# PROV-O namespace prefix (used as dict key prefix for clarity)
# ---------------------------------------------------------------------------

_PROV_NS = "prov"
_AGENT_ID = "kg-coach-dashboard:generator"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ProvODocument:
    """
    A PROV-O-shaped provenance document for one workout variant.

    Attributes
    ----------
    activity : dict
        prov:Activity capturing startedAtTime, endedAtTime, and the prompt/
        intent that triggered the generation run.
    agent : str
        prov:Agent id — the system component that produced the plan.
        (prov:wasAssociatedWith points here from the activity.)
    injury_state_used : dict | None
        Snapshot of the InjuryState that drove dynamic filtering, or None.
        Corresponds to the prov:used relationship from the Activity.
    healing_phase : str | None
        The active healing phase name (e.g. "remodeling") — the phase
        restrictions that were applied when filtering.
    per_exercise : list[dict]
        One prov:Entity per exercise IN the final plan. Each carries:
          - prov:entity_id   : exercise id
          - prov:label       : exercise name
          - prov:wasDerivedFrom : safe candidate pool id
          - prov:used        : the variant intent / structuring call
          - why              : per-exercise rationale (from WorkoutPlan)
          - sequencing_role  : functional role in the session arc
          - sequencing_rationale : why it sits at its position
    filtered_out : list[dict]
        One entry per exercise EXCLUDED by the safety filter. Each carries:
          - exercise_id      : catalog id
          - exercise_name    : human-readable name
          - reason           : the human-readable exclusion reason
          - graph_path       : list of node ids representing the traversal
                               path that justified exclusion (e.g.
                               ["knee", "patellofemoral_joint"])
          - injury_constraint : the specific pain_on movement type or phase
                               rule that fired (or None for equipment/dislike)
    """

    activity: dict[str, Any]
    agent: str
    injury_state_used: dict[str, Any] | None
    healing_phase: str | None
    per_exercise: list[dict[str, Any]]
    filtered_out: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_provenance(
    plan: WorkoutPlan,
    trace: ConditionalFilterTrace,
    constraints: dict[str, Any],
    timing: tuple[datetime, datetime],
    variant_id: str = "unknown",
    injury_joint: str | None = None,
) -> ProvODocument:
    """
    Build a PROV-O-shaped provenance document for one workout variant.

    Parameters
    ----------
    plan : WorkoutPlan
        The structured plan produced by the LLM for this variant.
    trace : ConditionalFilterTrace
        The shared safety-filter trace (safe, removed, injury_state_used, etc.).
    constraints : dict
        Contextual constraints dict with keys:
          - "prompt"                : str — the coach's original prompt
          - "member_id"             : str — member the plan was generated for
          - "time_window_minutes"   : int — requested session duration
          - "equipment_available"   : list[str] — member's equipment
          - "variant_id"            : str — "strength" | "conditioning" | "mobility"
    timing : tuple[datetime, datetime]
        (started_at, ended_at) UTC datetimes for the generation run.
    variant_id : str
        Redundant with constraints["variant_id"] — kept as explicit param for
        call-site clarity.
    injury_joint : str | None
        The catalog slug of the injured joint (e.g. "knee", "lumbar_spine"),
        used to build the graph_path for filtered-out exercises.

    Returns
    -------
    ProvODocument
        The PROV-O-shaped provenance document.
    """
    started_at, ended_at = timing

    # ------------------------------------------------------------------
    # prov:Activity
    # ------------------------------------------------------------------
    activity: dict[str, Any] = {
        f"{_PROV_NS}:type": "prov:Activity",
        f"{_PROV_NS}:id": f"activity:generate_workout_{variant_id}_{started_at.strftime('%Y%m%dT%H%M%SZ')}",
        f"{_PROV_NS}:startedAtTime": started_at.isoformat(),
        f"{_PROV_NS}:endedAtTime": ended_at.isoformat(),
        f"{_PROV_NS}:wasAssociatedWith": _AGENT_ID,
        "prompt": constraints.get("prompt", ""),
        "member_id": constraints.get("member_id", ""),
        "time_window_minutes": constraints.get("time_window_minutes", 60),
        "variant_id": constraints.get("variant_id", variant_id),
        "equipment_available": constraints.get("equipment_available", []),
    }

    # ------------------------------------------------------------------
    # injury_state_used (prov:used — the InjuryState input to the Activity)
    # ------------------------------------------------------------------
    injury_state_dict: dict[str, Any] | None = None
    injury_state: InjuryState | None = trace.injury_state_used
    if injury_state is not None:
        injury_state_dict = {
            f"{_PROV_NS}:type": "prov:Entity",
            f"{_PROV_NS}:id": f"entity:injury_state_{injury_state.injury_id}_{injury_state.recorded_at.strftime('%Y%m%dT%H%M%SZ')}",
            "injury_id": injury_state.injury_id,
            "recorded_at": injury_state.recorded_at.isoformat(),
            "inflammation": injury_state.inflammation,
            "pain_on": list(injury_state.pain_on),
            "subjective_pain": injury_state.subjective_pain,
            "load_tolerance_pct": injury_state.load_tolerance_pct,
            "notes": injury_state.notes,
        }

    # ------------------------------------------------------------------
    # per_exercise — one prov:Entity per exercise IN the plan
    # ------------------------------------------------------------------
    per_exercise: list[dict[str, Any]] = []

    # Build a flat list of all planned exercises across all sections
    all_planned = list(plan.warmup) + list(plan.main) + list(plan.cooldown)
    safe_candidate_pool_id = f"entity:safe_candidate_pool_{variant_id}"

    for pe in all_planned:
        ex_entity: dict[str, Any] = {
            f"{_PROV_NS}:type": "prov:Entity",
            f"{_PROV_NS}:id": f"entity:planned_exercise_{pe.exercise_id}_{variant_id}",
            f"{_PROV_NS}:label": pe.name,
            f"{_PROV_NS}:wasDerivedFrom": safe_candidate_pool_id,
            f"{_PROV_NS}:used": f"activity:generate_workout_{variant_id}_{started_at.strftime('%Y%m%dT%H%M%SZ')}",
            "exercise_id": pe.exercise_id,
            "section": _get_section(pe.exercise_id, plan),
            "order": pe.order,
            "sets": pe.sets,
            "reps": pe.reps,
            "duration_seconds": pe.duration_seconds,
            "rest_seconds": pe.rest_seconds,
            "why": pe.rationale,
            "sequencing_role": pe.sequencing_role,
            "sequencing_rationale": pe.sequencing_rationale,
        }
        per_exercise.append(ex_entity)

    # ------------------------------------------------------------------
    # filtered_out — one entry per exercise REMOVED by the safety gate
    # ------------------------------------------------------------------
    filtered_out: list[dict[str, Any]] = []

    for ex, reason in trace.removed:
        # Determine if this was an injury-driven exclusion
        injury_constraint: str | None = None
        graph_path: list[str] = []

        reason_lower = reason.lower()

        if "movement type" in reason_lower and injury_joint:
            # Movement-type exclusion — build the traversal path
            injury_constraint = _extract_movement_types_from_reason(reason)
            graph_path = _build_graph_path(injury_joint, ex.joints_loaded)
        elif "stresses injured joint" in reason_lower and injury_joint:
            # Conservative joint-level exclusion (unannotated)
            injury_constraint = f"stresses injured joint: {injury_joint}"
            graph_path = _build_graph_path(injury_joint, ex.joints_loaded)
        elif "equipment" in reason_lower:
            # Equipment gate
            injury_constraint = None
            graph_path = []
        elif "dislike" in reason_lower:
            injury_constraint = None
            graph_path = []
        elif "explicitly excluded" in reason_lower:
            injury_constraint = None
            graph_path = []

        filtered_entry: dict[str, Any] = {
            f"{_PROV_NS}:type": "prov:Entity",
            f"{_PROV_NS}:id": f"entity:filtered_exercise_{ex.id}",
            f"{_PROV_NS}:label": ex.name,
            "exercise_id": ex.id,
            "exercise_name": ex.name,
            "reason": reason,
            "graph_path": graph_path,
            "injury_constraint": injury_constraint,
        }
        filtered_out.append(filtered_entry)

    return ProvODocument(
        activity=activity,
        agent=_AGENT_ID,
        injury_state_used=injury_state_dict,
        healing_phase=trace.phase_restrictions_applied.get("phase_name"),
        per_exercise=per_exercise,
        filtered_out=filtered_out,
    )


def prov_document_to_dict(doc: ProvODocument) -> dict[str, Any]:
    """
    Serialise a ProvODocument to a JSON-safe dict.

    The dict shape uses PROV-O term names as keys (prefixed with "prov:")
    so that it can be embedded directly in API responses or saved as JSON-LD.
    """
    return {
        f"{_PROV_NS}:Activity": doc.activity,
        f"{_PROV_NS}:wasAssociatedWith": doc.agent,
        "injury_state_used": doc.injury_state_used,
        "healing_phase": doc.healing_phase,
        f"{_PROV_NS}:hadMember_per_exercise": doc.per_exercise,
        "filtered_out": doc.filtered_out,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_section(exercise_id: str, plan: WorkoutPlan) -> str:
    """Return 'warmup', 'main', or 'cooldown' for an exercise in the plan."""
    for pe in plan.warmup:
        if pe.exercise_id == exercise_id:
            return "warmup"
    for pe in plan.main:
        if pe.exercise_id == exercise_id:
            return "main"
    for pe in plan.cooldown:
        if pe.exercise_id == exercise_id:
            return "cooldown"
    return "unknown"


def _extract_movement_types_from_reason(reason: str) -> str:
    """
    Extract the movement types mentioned in an exclusion reason string.

    e.g. "movement type(s) ['flexion', 'load'] excluded at injured joint ..."
    → "movement types: ['flexion', 'load']"
    """
    import re

    match = re.search(r"movement type\(s\)\s+(\[.*?\])", reason)
    if match:
        return f"movement types: {match.group(1)}"
    return reason


def _build_graph_path(injury_joint: str, exercise_joints_loaded: list[str]) -> list[str]:
    """
    Build a representative graph traversal path for an injury-driven exclusion.

    The path represents: injured joint → descendant nodes → exercise joints.
    Used by the frontend ProvenanceTrace and Graph Explorer to highlight the
    part-of traversal chain that justified excluding an exercise.

    For example, for a knee injury + Barbell Squat (joints_loaded: ["Knee"]):
      ["knee", "patellofemoral_joint", "Knee"]

    This is a simplified representation — the full traversal uses the SNOMED
    anatomy graph; here we surface the concept-level path for human readability.
    """
    path: list[str] = [injury_joint]

    # Add known anatomical children of common injury joints
    _anatomy_children: dict[str, list[str]] = {
        "knee": ["patellofemoral_joint", "tibiofemoral_joint"],
        "lumbar_spine": ["lumbar_intervertebral_joint", "lumbar_disc"],
        "shoulder": ["glenohumeral_joint", "acromioclavicular_joint"],
        "hip": ["acetabulum", "femoral_head"],
        "ankle": ["talocrural_joint", "subtalar_joint"],
    }

    children = _anatomy_children.get(injury_joint, [])
    path.extend(children)

    # Add any exercise joints that overlap with the injury region
    for j in exercise_joints_loaded:
        j_lower = j.lower().strip()
        if j_lower not in path and injury_joint in j_lower:
            path.append(j_lower)

    return path
