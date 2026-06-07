"""
Movement Knowledge Graph (MovementKG)

Builds a networkx.MultiDiGraph that wires exercises to ontology concept nodes
via typed edges:

  Exercise --stresses-->  Joint     (the joint is loaded under stress)
  Exercise --targets-->   Muscle    (primary/secondary muscle groups)
  Exercise --requires-->  Equipment (physical gear needed)
  Exercise --uses-->      Pattern   (movement pattern category)

Edges also carry movement-type annotations on exercise→joint edges, enabling
the dynamic safety filter to exclude exercises by specific movement type
(flexion / extension / rotation / load / impact) rather than just by joint.

The graph shares concept nodes with the SNOMED anatomy graph: joint node ids
in MovementKG correspond to SNOMED concept codes where applicable, so
part-of traversal from the SNOMED loader maps directly to graph nodes.

Usage:
    kg = MovementKG(exercises, catalog, snomed)
    joint_set = kg.descendants_by_part_of("knee")   # e.g. {"knee", "patellofemoral_joint", ...}
    excluded  = kg.exercises_stressing(joint_set)    # set of exercise ids
    flexion_ex = kg.exercises_by_movement_type("knee", "flexion")
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import networkx as nx

from app.models.exercise import Exercise
from app.ontology.concepts import Concept
from app.ontology.loader import SnomedConcept, get_descendants_by_part_of

# ---------------------------------------------------------------------------
# Edge type constants (used as the 'relation' attribute on MultiDiGraph edges)
# ---------------------------------------------------------------------------

EDGE_STRESSES = "stresses"    # Exercise → Joint
EDGE_TARGETS = "targets"      # Exercise → Muscle
EDGE_REQUIRES = "requires"    # Exercise → Equipment
EDGE_USES = "uses"            # Exercise → Pattern
EDGE_PART_OF = "part-of"      # Joint/region → parent region (from SNOMED)
EDGE_INVOLVES = "involves"    # Injury → Joint/region (from SNOMED)


class MovementKG:
    """
    The Movement Knowledge Graph.

    Internally backed by a networkx.MultiDiGraph so that multiple edge types
    can exist between the same pair of nodes (e.g. an exercise that both
    "stresses" and "targets" the knee would have two edges, though that is
    a degenerate case — the edges carry different relation types).

    Node types:
      - exercise      : Exercise nodes, keyed by exercise id
      - joint         : Concept nodes of type "joint" or "body_region"
      - muscle        : Concept nodes of type "muscle"
      - equipment     : Concept nodes of type "equipment"
      - pattern       : Concept nodes of type "pattern"

    The graph is built once at startup and then treated as read-only.
    """

    def __init__(
        self,
        exercises: list[Exercise],
        concepts: dict[str, Concept],
        snomed: dict[str, SnomedConcept],
    ) -> None:
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()
        self._exercises: dict[str, Exercise] = {ex.id: ex for ex in exercises}
        self._concepts = concepts
        self._snomed = snomed

        # Derived index: exercise_id -> Exercise (duplicates _exercises; kept for clarity)
        self._exercise_index: dict[str, Exercise] = self._exercises

        self._build(exercises, concepts, snomed)

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build(
        self,
        exercises: list[Exercise],
        concepts: dict[str, Concept],
        snomed: dict[str, SnomedConcept],
    ) -> None:
        """Populate the MultiDiGraph from exercises, concepts, and SNOMED data."""

        # 1. Add all concept nodes
        for concept_id, concept in concepts.items():
            self._g.add_node(
                concept_id,
                node_type=concept.type,
                pref_label=concept.pref_label,
                snomed_code=concept.snomed_code,
            )

        # 2. Add SNOMED anatomy nodes (may overlap with concept nodes by SNOMED code)
        #    and part-of edges
        for code, snomed_concept in snomed.items():
            node_id = self._snomed_node_id(code, concepts)
            if not self._g.has_node(node_id):
                self._g.add_node(
                    node_id,
                    node_type=snomed_concept.type,
                    pref_label=snomed_concept.pref_label,
                    snomed_code=code,
                )
            for parent_code in snomed_concept.part_of:
                parent_id = self._snomed_node_id(parent_code, concepts)
                if not self._g.has_node(parent_id):
                    parent = snomed.get(parent_code)
                    if parent:
                        self._g.add_node(
                            parent_id,
                            node_type=parent.type,
                            pref_label=parent.pref_label,
                            snomed_code=parent_code,
                        )
                self._g.add_edge(node_id, parent_id, relation=EDGE_PART_OF)

        # 3. Add exercise nodes and edges to concepts
        for ex in exercises:
            self._g.add_node(
                ex.id,
                node_type="exercise",
                name=ex.name,
                priority_tier=ex.priority_tier,
            )
            self._wire_exercise(ex, concepts)

    def _wire_exercise(self, ex: Exercise, concepts: dict[str, Concept]) -> None:
        """Add stresses/targets/requires/uses edges for one exercise."""

        # Build a normalised slug → concept_id lookup for matching
        joint_slug_map = self._build_slug_map(concepts, "joint")
        muscle_slug_map = self._build_slug_map(concepts, "muscle")
        equipment_slug_map = self._build_slug_map(concepts, "equipment")
        pattern_slug_map = self._build_slug_map(concepts, "pattern")

        # stresses: joints_loaded -> joint concept nodes
        for joint_str in ex.joints_loaded:
            joint_id = self._resolve_label(joint_str, joint_slug_map)
            if joint_id:
                # Gather movement types for this joint from the annotation
                movement_types = ex.joint_movements.get(joint_str, [])
                self._g.add_edge(
                    ex.id,
                    joint_id,
                    relation=EDGE_STRESSES,
                    movement_types=movement_types,
                )

        # targets: muscle_groups -> muscle concept nodes
        for muscle_str in ex.muscle_groups:
            muscle_id = self._resolve_label(muscle_str, muscle_slug_map)
            if muscle_id:
                self._g.add_edge(ex.id, muscle_id, relation=EDGE_TARGETS)

        # requires: equipment_required -> equipment concept nodes
        for equip_str in ex.equipment_required:
            equip_id = self._resolve_label(equip_str, equipment_slug_map)
            if equip_id:
                self._g.add_edge(ex.id, equip_id, relation=EDGE_REQUIRES)

        # uses: movement_patterns -> pattern concept nodes
        for pattern_str in ex.movement_patterns:
            pattern_id = self._resolve_label(pattern_str, pattern_slug_map)
            if pattern_id:
                self._g.add_edge(ex.id, pattern_id, relation=EDGE_USES)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def descendants_by_part_of(self, joint_slug: str) -> set[str]:
        """
        Return a set of node ids that are (transitively) part-of the given
        joint slug (e.g. "knee").

        The returned set includes BOTH the raw SNOMED codes AND the
        corresponding catalog slug node ids (where a mapping exists), so that
        exercise edges to catalog nodes (e.g. "knee") are correctly caught by
        exercises_stressing().

        Example:
            kg.descendants_by_part_of("knee")
            # → {"knee", "49076000", "57714003", "182204001", ...}
              # "knee" is the catalog slug for SNOMED 49076000
        """
        concept = self._concepts.get(joint_slug)
        if concept is None:
            return set()

        snomed_code = concept.snomed_code
        if snomed_code is None:
            # No SNOMED code — return just the slug itself
            return {joint_slug}

        # Use the SNOMED traversal utility for child codes
        descendant_codes = get_descendants_by_part_of(self._snomed, snomed_code)

        # Build result set: start with the root slug and its SNOMED code
        result: set[str] = {joint_slug, snomed_code}

        # For each descendant SNOMED code, also add the catalog slug if mapped
        for code in descendant_codes:
            result.add(code)
            slug = self._snomed_node_id(code, self._concepts)
            result.add(slug)

        return result

    def exercises_stressing(self, joint_node_ids: set[str]) -> set[str]:
        """
        Return exercise ids that have a 'stresses' edge to any joint in
        joint_node_ids.

        joint_node_ids should be the output of descendants_by_part_of()
        or similar — a set of node ids (SNOMED codes or catalog slugs).
        """
        result: set[str] = set()
        for ex_id, ex in self._exercises.items():
            if not self._g.has_node(ex_id):
                continue
            for _, target, data in self._g.out_edges(ex_id, data=True):
                if data.get("relation") == EDGE_STRESSES and target in joint_node_ids:
                    result.add(ex_id)
                    break
        return result

    def exercises_by_movement_type(self, joint_slug: str, movement_type: str) -> set[str]:
        """
        Return exercise ids that perform the given movement_type at the
        specified joint.

        Uses the joint_movements annotation on the Exercise model, surfaced
        via the edge 'movement_types' attribute on stresses edges.

        Example:
            kg.exercises_by_movement_type("knee", "flexion")
            # → {exercise ids for squats, lunges, split squats, ...}
        """
        concept = self._concepts.get(joint_slug)
        if concept is None:
            return set()

        # Resolve to the node id used in the graph for this joint
        # The graph may use either the catalog slug or a SNOMED code
        target_node_ids: set[str] = {joint_slug}
        if concept.snomed_code:
            target_node_ids.add(concept.snomed_code)

        result: set[str] = set()
        for ex_id in self._exercises:
            if not self._g.has_node(ex_id):
                continue
            for _, target, data in self._g.out_edges(ex_id, data=True):
                if (
                    data.get("relation") == EDGE_STRESSES
                    and target in target_node_ids
                    and movement_type in data.get("movement_types", [])
                ):
                    result.add(ex_id)
                    break
        return result

    def get_exercise(self, exercise_id: str) -> Exercise | None:
        """Return the Exercise model for the given id, or None."""
        return self._exercises.get(exercise_id)

    def all_exercises(self) -> list[Exercise]:
        """Return all exercises in the graph."""
        return list(self._exercises.values())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_slug_map(concepts: dict[str, Concept], concept_type: str) -> dict[str, str]:
        """
        Build a normalised-label → concept_id lookup for concepts of the
        given type.

        Includes both pref_label and all alt_labels, normalised to lowercase
        stripped strings so matching is case/whitespace insensitive.
        """
        slug_map: dict[str, str] = {}
        for concept_id, concept in concepts.items():
            if concept.type != concept_type:
                continue
            slug_map[concept.pref_label.lower().strip()] = concept_id
            for alt in concept.alt_labels:
                slug_map[alt.lower().strip()] = concept_id
        return slug_map

    @staticmethod
    def _resolve_label(label: str, slug_map: dict[str, str]) -> str | None:
        """Look up a raw label string in a normalised slug map."""
        return slug_map.get(label.lower().strip())

    @staticmethod
    def _snomed_node_id(code: str, concepts: dict[str, Concept]) -> str:
        """
        Return the graph node id to use for a SNOMED concept code.

        Prefers the catalog slug (if the concept is present in the catalog
        with a matching snomed_code) so that exercises wired to catalog nodes
        share the same node as the SNOMED anatomy graph.  Falls back to the
        raw SNOMED code.
        """
        for concept_id, concept in concepts.items():
            if concept.snomed_code == code:
                return concept_id
        return code

    # ------------------------------------------------------------------
    # Introspection helpers (for tests and debugging)
    # ------------------------------------------------------------------

    @property
    def graph(self) -> nx.MultiDiGraph:
        """Expose the underlying networkx graph for testing / inspection."""
        return self._g

    def node_count(self) -> int:
        return self._g.number_of_nodes()

    def edge_count(self) -> int:
        return self._g.number_of_edges()
