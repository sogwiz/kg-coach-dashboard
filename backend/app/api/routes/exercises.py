"""
Exercises API route — Phase 13.

GET /api/exercises
    Return the full exercise catalog (base + hybrid).

    Each exercise is returned with the fields needed by the Creative Canvas
    picker and for general catalog browsing:
      id, name, movement_patterns, muscle_groups, equipment_required,
      joints_loaded, priority_tier

    Optional query parameters:
      ?search=<str>   — case-insensitive substring match against name and
                        movement_patterns strings.  Returns all exercises
                        whose name or any pattern contains the query.
      ?member_id=<id> — when given, each exercise is annotated with a
                        ``contraindicated`` boolean flag.  Uses the existing
                        MovementKG static contraindicated-for edges via
                        MovementKG.contraindicated_exercises() per injury
                        joint, identical to the graph route's member-aware
                        annotation logic.

Depends on:
  - app.data.loader.load_exercises
  - app.graph.movement_kg.MovementKG (built on demand; no singleton — the
    graph route and generator both build on demand too)
  - app.data.loader.load_member_context (for member_id path)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/exercises", tags=["exercises"])


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class ExerciseItem(BaseModel):
    id: str
    name: str
    movement_patterns: list[str]
    muscle_groups: list[str]
    equipment_required: list[str]
    joints_loaded: list[str]
    priority_tier: int
    contraindicated: bool = False   # only set when member_id is provided


class ExerciseListResponse(BaseModel):
    exercises: list[ExerciseItem]
    total: int
    member_id: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_kg(exercises):
    """Build a MovementKG from the given exercises list."""
    from app.ontology.catalog import build_concept_catalog
    from app.ontology.loader import load_snomed_anatomy
    from app.graph.movement_kg import MovementKG

    concepts = build_concept_catalog()
    snomed = load_snomed_anatomy()
    return MovementKG(exercises, concepts, snomed)


def _get_contraindicated_ids(member_id: str, kg) -> set[str]:
    """
    Return the set of exercise ids that are contraindicated for the given
    member, based on the member's injuries.

    Uses MovementKG.contraindicated_exercises() (static textbook view via the
    contraindicated-for edges) for each injury the member has.  This mirrors
    the graph route's _get_filtered_exercises_for_member logic — the same
    edges, the same helper.

    Falls back to an empty set if the member is not found or has no injuries.
    """
    try:
        from app.data.loader import load_member_context
        member = load_member_context(member_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not member.injuries:
        return set()

    contraindicated: set[str] = set()
    for raw_inj in member.injuries:
        joint = raw_inj.joint
        contra_ids = kg.contraindicated_exercises(joint)
        contraindicated |= contra_ids

    return contraindicated


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("", response_model=ExerciseListResponse)
async def list_exercises(
    search: str | None = Query(default=None, description="Case-insensitive substring match on name or movement_patterns"),
    member_id: str | None = Query(default=None, description="Member id; when given, flags contraindicated exercises"),
) -> ExerciseListResponse:
    """
    Return the full exercise catalog, optionally filtered by search term and
    annotated with contraindication status for a given member.

    The catalog includes all base exercises (exercises.json) merged with all
    hybrid exercises (exercises.hybrid.json), totalling 70+ items.

    When ?search= is provided, returns only exercises whose name or any of
    their movement_patterns strings contain the search term (case-insensitive).

    When ?member_id= is provided, each exercise carries a ``contraindicated``
    boolean based on the member's injury joints and the static
    contraindicated-for edges in the Movement KG.
    """
    from app.data.loader import load_exercises

    exercises = load_exercises()
    kg = _build_kg(exercises)

    # Member-aware contraindication set
    contraindicated_ids: set[str] = set()
    if member_id:
        contraindicated_ids = _get_contraindicated_ids(member_id, kg)

    # Apply search filter
    if search:
        search_lower = search.lower()
        exercises = [
            ex for ex in exercises
            if search_lower in ex.name.lower()
            or any(search_lower in p.lower() for p in ex.movement_patterns)
        ]

    items = [
        ExerciseItem(
            id=ex.id,
            name=ex.name,
            movement_patterns=ex.movement_patterns,
            muscle_groups=ex.muscle_groups,
            equipment_required=ex.equipment_required,
            joints_loaded=ex.joints_loaded,
            priority_tier=ex.priority_tier,
            contraindicated=(ex.id in contraindicated_ids),
        )
        for ex in exercises
    ]

    return ExerciseListResponse(
        exercises=items,
        total=len(items),
        member_id=member_id,
    )
