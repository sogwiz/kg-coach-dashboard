"""
Graph API route — Phase 10.

GET /api/graph
    Serialize the Movement/Clinical KG to {nodes, edges} for the Graph Explorer.

    Nodes: exercise / muscle / joint / pattern / equipment / injury_concept
           Each node carries: id, label, type, filtered_out? (when member_id given)

    Edges: stresses / targets / requires / part-of / uses / contraindicated-for
           Each edge carries: source, target, relation, on_filter_path? (member-aware)

    When ?member_id= is provided:
      - exercises that are filtered out for that member's current injury state are
        annotated with filtered_out=True
      - the part-of chain that caused the filtering is annotated with
        on_filter_path=True, letting the Graph Explorer highlight the
        provenance path in red

Depends on:
  - app.graph.movement_kg.MovementKG (singleton built at boot in app.data.loader)
  - app.data.loader.load_member_context / load_exercises / load_snomed
  - app.graph.conditional_filter.conditional_safety_filter (for member-aware annotation)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/graph", tags=["graph"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ExclusionAttribution(BaseModel):
    """Which injury (and graph reason) excluded an exercise for the member."""
    injury: str                   # human label, e.g. "left knee — patellofemoral pain syndrome"
    joint: str                    # injured joint slug, e.g. "knee"
    reason: str                   # the filter's reason string


class GraphNode(BaseModel):
    id: str
    label: str
    type: str                     # exercise / muscle / joint / pattern / equipment / injury_concept
    filtered_out: bool = False    # True when member_id given and exercise is excluded
    on_filter_path: bool = False  # True for part-of chain nodes leading to exclusion
    # When filtered_out for an injury, which injury(ies) + reason drove it.
    # Empty when the exclusion was equipment/dislike rather than injury.
    excluded_by: list[ExclusionAttribution] = []


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str                 # stresses / targets / requires / part-of / uses / contraindicated-for
    on_filter_path: bool = False  # True for part-of edges in the exclusion chain
    movement_types: list[str] = []  # movement types on stresses/contraindicated-for edges


class MemberInjury(BaseModel):
    """The active member's injury, surfaced so the Explorer can name it."""
    joint: str
    region: str
    diagnosis: str
    label: str                    # display label, e.g. "left knee — patellofemoral pain syndrome"
    healing_phase: str | None = None


class GraphPayload(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    member_id: str | None = None
    member_injuries: list[MemberInjury] = []  # the member's injuries (for the filter banner)
    filtered_exercise_ids: list[str] = []   # for the frontend toggle
    filter_path_node_ids: list[str] = []    # part-of chain node ids


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_movement_kg():
    """Build (or retrieve cached) the MovementKG singleton."""
    from app.data.loader import load_exercises
    from app.ontology.catalog import build_concept_catalog
    from app.ontology.loader import load_snomed_anatomy
    from app.graph.movement_kg import MovementKG

    exercises = load_exercises()
    concepts = build_concept_catalog()
    snomed = load_snomed_anatomy()
    return MovementKG(exercises, concepts, snomed)


def _injury_label(promoted) -> str:
    """Human display label for an injury, e.g. 'left knee — patellofemoral pain syndrome'.

    The seed `diagnosis` can be a long clinical note; we keep only the short
    clinical name (first clause) for the label.
    """
    region = (getattr(promoted, "region", "") or "").strip()
    diagnosis = (getattr(promoted, "diagnosis", "") or "").strip()
    short_dx = diagnosis.split(" — ")[0].split(". ")[0].strip()
    base = region or getattr(promoted, "joint", "injury")
    if short_dx and short_dx.lower() not in base.lower():
        return f"{base} — {short_dx}"
    return base


def _get_filtered_exercises_for_member(
    member_id: str, kg
) -> tuple[set[str], set[str], dict[str, list[dict]], list[dict]]:
    """
    Run the conditional safety filter for the member and return:
      (filtered_out_ids, filter_path_node_ids, exclusion_by_exercise, member_injuries)

    filtered_out_ids     — exercise ids removed by the safety filter
    filter_path_node_ids — node ids in the part-of chain that caused removal
    exclusion_by_exercise — exercise_id → list of {injury, joint, reason} for
                            INJURY-driven exclusions (equipment/dislike reasons
                            are not attributed to an injury)
    member_injuries      — the member's injuries (joint/region/diagnosis/label/phase)
    """
    from app.data.loader import load_member_context
    from app.api.routes.injury import _promote_injury
    from app.graph.conditional_filter import conditional_safety_filter
    from app.ontology.catalog import build_concept_catalog

    try:
        member = load_member_context(member_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not member.injuries:
        return set(), set(), {}, []

    build_concept_catalog()  # ensure catalog is warm (shared concept nodes)
    all_exercises = kg.all_exercises()
    equipment_available = set(member.equipment_available)
    dislikes = set(member.preferences.dislikes) if member.preferences else set()

    filtered_out_ids: set[str] = set()
    filter_path_node_ids: set[str] = set()
    exclusion_by_exercise: dict[str, list[dict]] = {}
    member_injuries: list[dict] = []

    for raw_inj in member.injuries:
        try:
            member_id_str = member.profile.id
            promoted = _promote_injury(raw_inj, member_id_str)
        except Exception:
            continue

        label = _injury_label(promoted)
        try:
            phase = promoted.computed_phase().value
        except Exception:
            phase = None
        member_injuries.append(
            {
                "joint": promoted.joint,
                "region": getattr(promoted, "region", "") or "",
                "diagnosis": getattr(promoted, "diagnosis", "") or "",
                "label": label,
                "healing_phase": phase,
            }
        )

        try:
            trace = conditional_safety_filter(
                candidates=all_exercises,
                injury=promoted,
                available_equipment=equipment_available,
                excluded_ids=set(),
                dislikes=dislikes,
                kg=kg,
            )
        except Exception:
            continue

        # Collect removed exercise ids; attribute INJURY-driven removals to this
        # injury. Equipment/dislike/explicit removals are not injury-attributed.
        for ex, reason in trace.removed:
            filtered_out_ids.add(ex.id)
            if "injured joint" in reason:
                exclusion_by_exercise.setdefault(ex.id, []).append(
                    {"injury": label, "joint": promoted.joint, "reason": reason}
                )

        # Collect the part-of chain nodes that caused filtering
        injury_joint = promoted.joint
        joint_descendants = kg.descendants_by_part_of(injury_joint)
        filter_path_node_ids.update(joint_descendants)
        filter_path_node_ids.add(f"injury_concept_{injury_joint}")

    return filtered_out_ids, filter_path_node_ids, exclusion_by_exercise, member_injuries


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("", response_model=GraphPayload)
async def get_graph(
    member_id: str | None = Query(default=None, description="Member id for member-aware filtering annotation")
) -> GraphPayload:
    """
    Return the full Movement/Clinical Knowledge Graph as {nodes, edges}.

    When member_id is provided, exercises that would be filtered out for that
    member's current injury state are annotated with filtered_out=True, and
    the part-of chain that caused the filtering is annotated with
    on_filter_path=True.

    This powers two Graph Explorer features:
      1. Provenance: member-aware toggle dims/reddens removed exercises
      2. Explainability: click any exercise to see its concept edges
    """
    kg = _build_movement_kg()
    graph = kg.graph

    # Member-aware filtering
    filtered_out_ids: set[str] = set()
    filter_path_node_ids: set[str] = set()
    exclusion_by_exercise: dict[str, list[dict]] = {}
    member_injuries: list[dict] = []
    if member_id:
        (
            filtered_out_ids,
            filter_path_node_ids,
            exclusion_by_exercise,
            member_injuries,
        ) = _get_filtered_exercises_for_member(member_id, kg)

    # ---------------------------------------------------------------------------
    # Build nodes
    # ---------------------------------------------------------------------------
    nodes: list[GraphNode] = []
    seen_nodes: set[str] = set()

    for node_id, data in graph.nodes(data=True):
        if node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)

        node_type = data.get("node_type", "unknown")
        # Derive a human-readable label
        label = (
            data.get("pref_label")
            or data.get("name")
            or str(node_id)
        )

        filtered_out = node_id in filtered_out_ids
        on_filter_path = node_id in filter_path_node_ids
        excluded_by = [
            ExclusionAttribution(**entry)
            for entry in exclusion_by_exercise.get(node_id, [])
        ]

        nodes.append(GraphNode(
            id=node_id,
            label=label,
            type=node_type,
            filtered_out=filtered_out,
            on_filter_path=on_filter_path,
            excluded_by=excluded_by,
        ))

    # ---------------------------------------------------------------------------
    # Build edges
    # ---------------------------------------------------------------------------
    edges: list[GraphEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()

    for source, target, data in graph.edges(data=True):
        relation = data.get("relation", "unknown")
        edge_key = (source, target, relation)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)

        movement_types = data.get("movement_types", [])

        # A part-of edge is on the filter path when BOTH source and target
        # are in the filter path node set
        is_filter_path_edge = (
            relation == "part-of"
            and source in filter_path_node_ids
            and target in filter_path_node_ids
        )

        edges.append(GraphEdge(
            source=source,
            target=target,
            relation=relation,
            on_filter_path=is_filter_path_edge,
            movement_types=list(movement_types) if movement_types else [],
        ))

    return GraphPayload(
        nodes=nodes,
        edges=edges,
        member_id=member_id,
        member_injuries=[MemberInjury(**inj) for inj in member_injuries],
        filtered_exercise_ids=sorted(filtered_out_ids),
        filter_path_node_ids=sorted(filter_path_node_ids),
    )
