"""
Movement Knowledge Graph (MovementKG)

Builds a networkx.MultiDiGraph that wires exercises to ontology concept nodes
via typed edges:

  Exercise  --stresses-->          Joint     (the joint is loaded under stress)
  Exercise  --targets-->           Muscle    (primary/secondary muscle groups)
  Exercise  --requires-->          Equipment (physical gear needed)
  Exercise  --uses-->              Pattern   (movement pattern category)
  InjuryConcept --contraindicated-for--> Exercise  (static textbook view)

Edges also carry movement-type annotations on exercise→joint edges, enabling
the dynamic safety filter to exclude exercises by specific movement type
(flexion / extension / rotation / load / impact) rather than just by joint.

The graph shares concept nodes with the SNOMED anatomy graph: joint node ids
in MovementKG correspond to SNOMED concept codes where applicable, so
part-of traversal from the SNOMED loader maps directly to graph nodes.

Phase 7.1 addition (R3 KG1 gap-closing):
  Materialize static ``contraindicated-for`` edges from a small built-in table
  of injury–concept → excluded movement-types rules.  These are the static
  "textbook" contraindications (not state-aware); the dynamic
  conditional_safety_filter remains the runtime authority for today's injury.
  The edges power the Graph Explorer (Phase 10) and satisfy the literal KG1
  edge-type spec.

Usage:
    kg = MovementKG(exercises, catalog, snomed)
    joint_set  = kg.descendants_by_part_of("knee")
    excluded   = kg.exercises_stressing(joint_set)
    flexion_ex = kg.exercises_by_movement_type("knee", "flexion")

    # Contraindicated-for (static textbook view)
    contra = kg.contraindicated_exercises("knee")
    # → {exercise_id, ...}  — exercises with static knee contra edges

    edges = kg.list_contraindicated_for_edges()
    # → [{injury_concept, exercise_id, exercise_name, movement_types}, ...]
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

EDGE_STRESSES = "stresses"              # Exercise → Joint
EDGE_TARGETS = "targets"               # Exercise → Muscle
EDGE_REQUIRES = "requires"             # Exercise → Equipment
EDGE_USES = "uses"                     # Exercise → Pattern
EDGE_PART_OF = "part-of"               # Joint/region → parent region (from SNOMED)
EDGE_INVOLVES = "involves"             # Injury → Joint/region (from SNOMED)
EDGE_CONTRAINDICATED_FOR = "contraindicated-for"  # InjuryConcept → Exercise (static textbook)


# ---------------------------------------------------------------------------
# Static textbook contraindication rules (R3 KG1 gap-closing)
#
# Maps an injury joint slug → list of movement-types that are baseline
# contraindicated for that injury, based on standard rehab/clinical guidelines.
# The dynamic conditional_safety_filter overrides these at runtime using the
# member's actual injury state (pain_on, inflammation, phase).
#
# Format: injury_joint_slug → set of contraindicated movement types
# ---------------------------------------------------------------------------

_STATIC_CONTRAINDICATION_RULES: dict[str, set[str]] = {
    "knee": {"flexion", "impact", "load"},
    "lumbar_spine": {"flexion", "load", "rotation"},
    "shoulder": {"flexion", "rotation", "load"},
    "hip": {"flexion", "load"},
    "ankle": {"impact", "load"},
}


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

        # 4. Materialize static contraindicated-for edges (R3 KG1 gap-closing)
        self._build_contraindicated_for_edges(exercises, concepts)

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

    def _build_contraindicated_for_edges(
        self,
        exercises: list[Exercise],
        concepts: dict[str, Concept],
    ) -> None:
        """
        Materialize static ``contraindicated-for`` edges from the baseline
        clinical rules table (_STATIC_CONTRAINDICATION_RULES).

        For each injury joint slug in the rules table:
          1. Add an injury-concept node (node_type="injury_concept") if absent.
          2. For each exercise that involves that joint with a contraindicated
             movement type, add edge:
               injury_concept_node --contraindicated-for--> exercise_node
             The edge carries ``movement_types`` (which types triggered it).

        Two sources are checked for an exercise's involvement with a joint:
          a. Graph stresses edges (joints in exercise.joints_loaded) — the
             primary source used by the safety filter.
          b. The exercise.joint_movements annotation dict — covers joints
             that appear in annotations but were omitted from joints_loaded
             (e.g. lumbar_spine annotations on exercises whose joints_loaded
             lists only the primary joint).  This ensures the static contra
             edges are complete even when joints_loaded is not exhaustive.

        These are static "textbook" edges — the runtime authority is always
        the conditional_safety_filter with today's injury state.
        """
        for joint_slug, contra_movement_types in _STATIC_CONTRAINDICATION_RULES.items():
            # Ensure the injury-concept node exists
            inj_concept_id = f"injury_concept_{joint_slug}"
            if not self._g.has_node(inj_concept_id):
                label = f"{joint_slug.replace('_', ' ')} injury"
                self._g.add_node(
                    inj_concept_id,
                    node_type="injury_concept",
                    pref_label=label,
                    joint_slug=joint_slug,
                )

            # Collect all node ids for this joint (slug + SNOMED descendants)
            joint_node_ids = self.descendants_by_part_of(joint_slug)

            # Walk every exercise: find ones that involve this joint with a
            # movement type that appears in the contraindication rule.
            for ex in exercises:
                if not self._g.has_node(ex.id):
                    continue
                triggered_types: set[str] = set()

                # Source (a): check graph stresses edges
                for _, target, data in self._g.out_edges(ex.id, data=True):
                    if data.get("relation") != EDGE_STRESSES:
                        continue
                    if target not in joint_node_ids:
                        continue
                    ex_movement_types = set(data.get("movement_types", []))
                    matched = ex_movement_types & contra_movement_types
                    if matched:
                        triggered_types |= matched

                # Source (b): check joint_movements annotation directly
                # (covers joints listed in annotations but not in joints_loaded)
                for annotated_joint, movement_type_list in ex.joint_movements.items():
                    # Match by joint slug directly
                    if annotated_joint == joint_slug:
                        matched = set(movement_type_list) & contra_movement_types
                        if matched:
                            triggered_types |= matched

                if triggered_types:
                    self._g.add_edge(
                        inj_concept_id,
                        ex.id,
                        relation=EDGE_CONTRAINDICATED_FOR,
                        movement_types=sorted(triggered_types),
                    )

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

    def contraindicated_exercises(self, injury_joint_slug: str) -> set[str]:
        """
        Return the set of exercise ids that are statically contraindicated for
        the given injury joint slug (e.g. "knee", "lumbar_spine").

        These edges are the static "textbook" view materialised at graph-build
        time from _STATIC_CONTRAINDICATION_RULES.  The runtime authority for
        a specific member's injury state is the conditional_safety_filter.

        Parameters
        ----------
        injury_joint_slug:
            The joint concept id (e.g. "knee", "lumbar_spine").

        Returns
        -------
        set[str]
            Exercise ids with a ``contraindicated-for`` edge from the given
            injury concept node.  Empty set if no rules exist for the slug.
        """
        inj_concept_id = f"injury_concept_{injury_joint_slug}"
        if not self._g.has_node(inj_concept_id):
            return set()
        result: set[str] = set()
        for _, target, data in self._g.out_edges(inj_concept_id, data=True):
            if data.get("relation") == EDGE_CONTRAINDICATED_FOR:
                result.add(target)
        return result

    def list_contraindicated_for_edges(self) -> list[dict]:
        """
        Return all static ``contraindicated-for`` edges as a list of dicts.

        Each dict has:
          - injury_concept:  the injury concept node id (e.g. "injury_concept_knee")
          - joint_slug:      the joint slug (e.g. "knee")
          - exercise_id:     the exercise node id
          - exercise_name:   the exercise's human-readable name
          - movement_types:  list of movement types that triggered the edge

        Intended for the /api/graph endpoint (Phase 10 Graph Explorer) to
        render the static contraindication graph alongside the dynamic safety
        filter result.
        """
        edges: list[dict] = []
        for source, target, data in self._g.edges(data=True):
            if data.get("relation") != EDGE_CONTRAINDICATED_FOR:
                continue
            source_data = self._g.nodes.get(source, {})
            ex = self._exercises.get(target)
            if ex is None:
                continue
            edges.append({
                "injury_concept": source,
                "joint_slug": source_data.get("joint_slug", ""),
                "exercise_id": target,
                "exercise_name": ex.name,
                "movement_types": data.get("movement_types", []),
            })
        return edges

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
