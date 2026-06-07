"""
Member Context KG — Phase 7 + 7.1 (R2/R3 gap-closing).

Models a member's context as graph nodes that SHARE concept nodes (joint,
equipment) with the Movement KG.  This allows queries like "what equipment
does this member have?" or "what joints are injured?" to be answered via
graph traversal, and the shared concept nodes link member context to the
movement/safety graph.

The Member KG is intentionally thin — its value is the unified query API
that the Copilot agent tools use, not complex graph algorithms.

Phase 7.1 additions (R3 KG2 gap-closing):
  - get_goals()            → list[Goal]
  - get_preferences()      → Preferences
  - get_lab_results()      → Labs  (blood panel + DEXA scan)
  - get_workout_history()  → list[WorkoutSession]
  - get_chat_history()     → list[ChatMessage]
  - get_biomarkers()       now returns full Biomarkers incl. RHR/HRV/sleep

Usage
-----
    from app.graph.member_kg import MemberKG
    from app.data.loader import load_member_context
    from app.ontology.catalog import build_concept_catalog

    member = load_member_context("mbr_01HX9JORDAN")
    concepts = build_concept_catalog()
    mkg = MemberKG(member, concepts)

    injuries   = mkg.get_injuries()       # list[Injury]  (promoted full model)
    adherence  = mkg.get_adherence_series(weeks=4)
    equipment  = mkg.get_equipment()      # set[str]
    brief      = mkg.get_coach_brief()    # CoachBrief
    biomarkers = mkg.get_biomarkers()     # Biomarkers (RHR, HRV, sleep, weight)
    goals      = mkg.get_goals()          # list[Goal]
    prefs      = mkg.get_preferences()   # Preferences
    labs       = mkg.get_lab_results()   # Labs (blood_panel + dexa_scan)
    history    = mkg.get_workout_history() # list[WorkoutSession]
    chat       = mkg.get_chat_history()  # list[ChatMessage]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING

import networkx as nx

from app.models.member import CoachBrief, MemberContext
from app.ontology.concepts import Concept

if TYPE_CHECKING:
    from app.models.injury import Injury
    from app.models.member import Biomarkers, ChatMessage, Goal, Labs, Preferences, WorkoutSession


# ---------------------------------------------------------------------------
# Lightweight adherence point (avoids importing WeeklyCompletion elsewhere)
# ---------------------------------------------------------------------------


@dataclass
class AdherencePoint:
    """A single week's adherence data point."""

    week_of: str  # ISO date string for the Monday of the week
    pct: float    # completion percentage (0.0–100.0)


# ---------------------------------------------------------------------------
# MemberKG
# ---------------------------------------------------------------------------


class MemberKG:
    """
    The Member Context Knowledge Graph.

    Backed by a networkx.DiGraph that shares joint and equipment concept
    nodes with the Movement KG.  The member node is the root; injury nodes
    link to joint concept nodes; equipment nodes link to the shared equipment
    concepts.

    Node types (node_type attribute):
      - member      : the member root node
      - injury      : a member injury, linked to a joint concept node
      - equipment   : equipment available to the member (shared with Movement KG)

    The graph is built once at init and treated as read-only thereafter.
    """

    def __init__(
        self,
        member: MemberContext,
        shared_concepts: dict[str, Concept],
    ) -> None:
        self._member = member
        self._concepts = shared_concepts
        self._g: nx.DiGraph = nx.DiGraph()
        self._injuries: list[Injury] = []  # promoted full Injury models

        self._build()

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Populate the DiGraph from member context + shared concept nodes."""
        member = self._member
        member_id = member.profile.id

        # 1. Member root node
        self._g.add_node(
            member_id,
            node_type="member",
            name=member.profile.name,
        )

        # 2. Shared concept nodes (joints, equipment, etc.)
        for concept_id, concept in self._concepts.items():
            if not self._g.has_node(concept_id):
                self._g.add_node(
                    concept_id,
                    node_type=concept.type,
                    pref_label=concept.pref_label,
                    snomed_code=concept.snomed_code,
                )

        # 3. Injury nodes — promoted to full Injury model, linked to joint concept
        from app.api.routes.injury import _promote_injury  # lazy to avoid circular

        promoted: list[Injury] = []
        for raw_inj in member.injuries:
            try:
                inj = _promote_injury(raw_inj, member_id)
                promoted.append(inj)
            except Exception:
                continue

        self._injuries = promoted

        for inj in promoted:
            inj_node_id = f"injury_{inj.id}"
            self._g.add_node(
                inj_node_id,
                node_type="injury",
                injury_id=inj.id,
                joint=inj.joint,
                diagnosis=inj.diagnosis,
                region=inj.region,
            )
            # Link member → injury
            self._g.add_edge(member_id, inj_node_id, relation="has_injury")
            # Link injury → shared joint concept node (if exists)
            if inj.joint in self._concepts:
                self._g.add_edge(
                    inj_node_id,
                    inj.joint,
                    relation="affects_joint",
                )

        # 4. Equipment nodes — member's available equipment linked to shared concepts
        joint_slug_map = {
            concept.pref_label.lower().strip(): cid
            for cid, concept in self._concepts.items()
            if concept.type == "equipment"
        }
        for equip_str in member.equipment_available:
            equip_slug = equip_str.lower().strip()
            concept_id = joint_slug_map.get(equip_slug)
            if concept_id and self._g.has_node(concept_id):
                # Link member → shared equipment concept
                self._g.add_edge(member_id, concept_id, relation="has_equipment")
            else:
                # Equipment not in catalog — add as a local node
                local_id = f"equip_{equip_slug.replace(' ', '_')}"
                if not self._g.has_node(local_id):
                    self._g.add_node(
                        local_id,
                        node_type="equipment",
                        pref_label=equip_str,
                    )
                self._g.add_edge(member_id, local_id, relation="has_equipment")

        # 5. Goal nodes — one node per goal, linked to member
        for goal in member.goals:
            goal_node_id = f"goal_{goal.id}"
            self._g.add_node(
                goal_node_id,
                node_type="goal",
                goal_id=goal.id,
                text=goal.text,
                priority=goal.priority,
                target_date=goal.target_date,
            )
            self._g.add_edge(member_id, goal_node_id, relation="has_goal")

        # 6. Workout-history nodes — one per session, linked to member
        for session in member.workout_history:
            sess_node_id = f"session_{member_id}_{session.date}"
            self._g.add_node(
                sess_node_id,
                node_type="workout_session",
                date=session.date,
                title=session.title,
                completed=session.completed,
                duration_min=session.duration_min,
                rpe=session.rpe,
            )
            self._g.add_edge(member_id, sess_node_id, relation="has_workout_session")

        # 7. Chat-history nodes — one per message, linked to member
        for msg in member.chat_history:
            # Use ts as unique-enough id (ts + sender)
            msg_node_id = f"chat_{member_id}_{msg.ts}_{msg.from_}"
            self._g.add_node(
                msg_node_id,
                node_type="chat_message",
                ts=msg.ts,
                from_=msg.from_,
                text=msg.text,
                has_attachments=len(msg.attachments) > 0,
            )
            self._g.add_edge(member_id, msg_node_id, relation="has_chat_message")

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_injuries(self) -> list[Injury]:
        """
        Return the member's injuries as promoted full Injury models.

        These carry onset_date, healing phase, and states time series.
        The injury nodes in the graph link to the shared joint concept nodes,
        enabling cross-graph traversal from member context to Movement KG.
        """
        return list(self._injuries)

    def get_adherence_series(self, weeks: int = 4) -> list[AdherencePoint]:
        """
        Return the most recent N weeks of adherence data.

        Parameters
        ----------
        weeks:
            Number of weeks to return (newest first).  Defaults to 4.

        Returns
        -------
        list[AdherencePoint]
            Up to ``weeks`` data points, newest first.
        """
        series = self._member.adherence.weekly_completion_pct
        # Convert to AdherencePoint and return the most recent N weeks
        points = [
            AdherencePoint(week_of=w.week_of, pct=w.pct)
            for w in series
        ]
        # newest first — sort by week_of descending
        points.sort(key=lambda p: p.week_of, reverse=True)
        return points[:weeks]

    def get_equipment(self) -> set[str]:
        """
        Return the set of equipment strings available to the member.

        These are the raw strings from the member context (not normalised
        concept slugs), suitable for display.
        """
        return set(self._member.equipment_available)

    def get_coach_brief(self) -> CoachBrief:
        """
        Return the member's coach brief.

        Contains morning_tasks and churn_risk, used by the morning_brief tool.
        """
        return self._member.coach_brief

    def get_biomarkers(self) -> "Biomarkers":
        """
        Return the member's latest biomarker data.

        Contains resting_hr_bpm, hrv_ms, sleep_hours_last_7_days,
        weight_trend_kg.  All fields are sourced directly from the member
        context — the Copilot reads these values verbatim (no fabrication).
        """
        return self._member.biomarkers

    def get_goals(self) -> "list[Goal]":
        """
        Return the member's goals (R3 KG2 — goals node).

        Each Goal has: id, text, priority, target_date.
        Goals are also represented as nodes in the KG linked via has_goal edges.
        """
        from app.models.member import Goal
        return list(self._member.goals)

    def get_preferences(self) -> "Preferences":
        """
        Return the member's training preferences (R3 KG2 — preferences node).

        Contains preferred_session_minutes, training_days_per_week,
        preferred_days, dislikes, notes.
        """
        from app.models.member import Preferences
        return self._member.preferences

    def get_lab_results(self) -> "Labs":
        """
        Return the member's latest lab results (R3 KG2 — labs node).

        Contains blood_panel (lipids, HbA1c, vitamin D, ferritin, CRP,
        and hormone panel where applicable) and dexa_scan (body composition).
        Either sub-field may be None if not available for this member.
        """
        from app.models.member import Labs
        return self._member.labs

    def get_workout_history(self) -> "list[WorkoutSession]":
        """
        Return the member's logged workout sessions (R3 KG2 — workout history).

        Each WorkoutSession has: date, title, planned, completed,
        duration_min, rpe, exercises (list of exercise name strings).
        Sessions are also represented as nodes linked via has_workout_session edges.
        """
        from app.models.member import WorkoutSession
        return list(self._member.workout_history)

    def get_chat_history(self) -> "list[ChatMessage]":
        """
        Return the member's chat history (R3 KG2 — chat history, R2 history).

        Each ChatMessage has: ts, from_ (member/coach), text, attachments.
        Attachments carry type and optional caption (images for multimodal).
        Messages are also represented as nodes linked via has_chat_message edges.
        """
        from app.models.member import ChatMessage
        return list(self._member.chat_history)

    def get_member_id(self) -> str:
        """Return the member's stable id."""
        return self._member.profile.id

    def get_member_name(self) -> str:
        """Return the member's display name."""
        return self._member.profile.name

    def injury_joint_concept_nodes(self) -> dict[str, str]:
        """
        Return a mapping of injury_id -> joint concept node id for all
        injuries that have a linked concept node.

        Used in tests to verify that injury nodes share concept nodes with
        the Movement KG.
        """
        result: dict[str, str] = {}
        member_id = self._member.profile.id
        for _, target, data in self._g.out_edges(member_id, data=True):
            if data.get("relation") != "has_injury":
                continue
            inj_node_data = self._g.nodes.get(target, {})
            if inj_node_data.get("node_type") != "injury":
                continue
            # Find the joint concept linked from this injury node
            for _, joint_target, edge_data in self._g.out_edges(target, data=True):
                if edge_data.get("relation") == "affects_joint":
                    inj_id = inj_node_data.get("injury_id", "")
                    result[inj_id] = joint_target
        return result

    # ------------------------------------------------------------------
    # Introspection (tests / debugging)
    # ------------------------------------------------------------------

    @property
    def graph(self) -> nx.DiGraph:
        """Expose the underlying networkx graph for testing / inspection."""
        return self._g

    def node_count(self) -> int:
        return self._g.number_of_nodes()

    def edge_count(self) -> int:
        return self._g.number_of_edges()
