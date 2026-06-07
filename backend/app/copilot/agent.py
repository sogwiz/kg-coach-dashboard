"""
Copilot agent — Phase 7 + 7.1 (R2/R3 gap-closing).

A LangGraph tool-calling (ReAct) agent that answers coach questions about a
member's context by calling tools backed by the Member KG.

Tools (Phase 7 originals)
--------------------------
  adherence_trend(member_id, weeks=4)
  morning_brief(member_id)
  injury_status(member_id)
  sleep_summary(member_id)
  current_workout_plan(member_id, variant_id=None)

Tools (Phase 7.1 additions — R2/R3 gap-closing)
-------------------------------------------------
  lab_results(member_id)
      Return blood panel + DEXA body-composition from the Member KG.
  body_composition(member_id)
      Return DEXA body-composition data specifically.
  workout_history(member_id, limit=10)
      Return the member's recent logged workout sessions.
  goals_and_preferences(member_id)
      Return the member's goals and training preferences.
  chat_history_search(member_id, query)
      Return recent chat messages, optionally filtered by query term.

R2 gap-closing (conversation memory + history + images)
--------------------------------------------------------
  - Agent is compiled with a MemorySaver checkpointer; invoked with
    config={"configurable": {"thread_id": member_id}} so multi-turn
    context persists per member.
  - On the first turn for a member's thread, seed/replay the member's
    seed chat_history into the conversation context.
  - CopilotRequest now accepts attachments: list[ChatAttachment]; image
    attachments are passed to the model as Anthropic vision content blocks.

Anti-fabrication
----------------
The system prompt explicitly instructs the agent to answer only from
tool/KG data and to say when the data doesn't support an answer.

LangSmith tracing
-----------------
Each agent invocation passes a RunnableConfig from tracing_config() so runs
appear tagged with member_id in the LangSmith dashboard.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------


def get_copilot_llm():
    """
    Return a LangChain ChatAnthropic model for the copilot agent.

    Uses claude-haiku-4-5 (same as the generator — fast, cheap, tool-capable,
    and vision-capable for multimodal attachments).

    Returns
    -------
    BaseChatModel or None
        None when ANTHROPIC_API_KEY is not set (callers skip gracefully).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(  # type: ignore[call-arg]
            model="claude-haiku-4-5",
            temperature=0.3,
            api_key=api_key,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tool functions (pure, no side effects — backed by MemberKG + store)
# ---------------------------------------------------------------------------
# Note: these are plain functions.  The @tool decorator is applied when
# building the agent so we can test the functions directly without the
# LangChain tool machinery.


def adherence_trend(member_id: str, weeks: int = 4) -> dict:
    """
    Return the member's session adherence trend for the past N weeks.

    Parameters
    ----------
    member_id: The member's stable id.
    weeks: Number of weeks to look back (default 4).

    Returns a dict with keys: member_id, trend, weekly_data (list of
    {week_of, pct} dicts), average_pct.
    """
    from app.data.loader import load_member_context
    try:
        member = load_member_context(member_id)
    except ValueError:
        return {"error": f"Member '{member_id}' not found"}

    from app.ontology.catalog import build_concept_catalog
    from app.graph.member_kg import MemberKG
    concepts = build_concept_catalog()
    mkg = MemberKG(member, concepts)

    series = mkg.get_adherence_series(weeks=weeks)
    avg = sum(p.pct for p in series) / len(series) if series else 0.0

    return {
        "member_id": member_id,
        "member_name": member.profile.name,
        "trend": member.adherence.trend,
        "weeks_requested": weeks,
        "weekly_data": [{"week_of": p.week_of, "pct": p.pct} for p in series],
        "average_pct": round(avg, 1),
    }


def morning_brief(member_id: str) -> dict:
    """
    Return the coach's morning brief for the member.

    Includes morning tasks and churn risk level.

    Parameters
    ----------
    member_id: The member's stable id.
    """
    from app.data.loader import load_member_context
    try:
        member = load_member_context(member_id)
    except ValueError:
        return {"error": f"Member '{member_id}' not found"}

    from app.ontology.catalog import build_concept_catalog
    from app.graph.member_kg import MemberKG
    concepts = build_concept_catalog()
    mkg = MemberKG(member, concepts)

    brief = mkg.get_coach_brief()

    return {
        "member_id": member_id,
        "member_name": member.profile.name,
        "generated_for": brief.generated_for,
        "morning_tasks": [
            {"type": t.type, "text": t.text}
            for t in brief.morning_tasks
        ],
        "churn_risk": {
            "level": brief.churn_risk.level,
            "reasons": brief.churn_risk.reasons,
        },
    }


def injury_status(member_id: str) -> dict:
    """
    Return the member's active injuries with current healing phase and
    latest check-in state.

    Parameters
    ----------
    member_id: The member's stable id.
    """
    from app.data.loader import load_member_context
    try:
        member = load_member_context(member_id)
    except ValueError:
        return {"error": f"Member '{member_id}' not found"}

    from app.ontology.catalog import build_concept_catalog
    from app.graph.member_kg import MemberKG
    concepts = build_concept_catalog()
    mkg = MemberKG(member, concepts)

    injuries = mkg.get_injuries()

    injury_list = []
    for inj in injuries:
        state = inj.current_state()
        injury_list.append({
            "id": inj.id,
            "region": inj.region,
            "joint": inj.joint,
            "diagnosis": inj.diagnosis,
            "onset_date": inj.onset_date.isoformat(),
            "days_since_onset": inj.days_since_onset(),
            "current_phase": inj.computed_phase().value,
            "latest_state": (
                {
                    "recorded_at": state.recorded_at.isoformat(),
                    "inflammation": state.inflammation,
                    "pain_on": state.pain_on,
                    "subjective_pain": state.subjective_pain,
                    "load_tolerance_pct": state.load_tolerance_pct,
                    "notes": state.notes,
                }
                if state is not None
                else None
            ),
        })

    return {
        "member_id": member_id,
        "member_name": member.profile.name,
        "active_injuries": injury_list,
        "injury_count": len(injury_list),
    }


def sleep_summary(member_id: str) -> dict:
    """
    Return the member's sleep data for the past 7 days.

    Parameters
    ----------
    member_id: The member's stable id.
    """
    from app.data.loader import load_member_context
    try:
        member = load_member_context(member_id)
    except ValueError:
        return {"error": f"Member '{member_id}' not found"}

    from app.ontology.catalog import build_concept_catalog
    from app.graph.member_kg import MemberKG
    concepts = build_concept_catalog()
    mkg = MemberKG(member, concepts)

    biomarkers = mkg.get_biomarkers()
    sleep_data = biomarkers.sleep_hours_last_7_days

    avg_sleep = sum(sleep_data) / len(sleep_data) if sleep_data else 0.0
    min_sleep = min(sleep_data) if sleep_data else 0.0
    max_sleep = max(sleep_data) if sleep_data else 0.0

    return {
        "member_id": member_id,
        "member_name": member.profile.name,
        "sleep_hours_last_7_days": sleep_data,
        "average_sleep_hours": round(avg_sleep, 1),
        "min_sleep_hours": round(min_sleep, 1),
        "max_sleep_hours": round(max_sleep, 1),
        "resting_hr_bpm": biomarkers.resting_hr_bpm,
        "hrv_ms": biomarkers.hrv_ms,
    }


def current_workout_plan(member_id: str, variant_id: str | None = None) -> dict:
    """
    Read the most recently generated plan from the Phase 6 store.

    Returns all 3 variants (or a specific one if variant_id is given), each
    with:
      - session-level stimulus / target_adaptation / design_rationale
      - per-exercise rationale + sequencing_rationale for every exercise
      - safety-filter provenance: what was excluded and why

    The coach can ask "why these exercises / why this order / what stimulus /
    compare the variants" and the Copilot grounds its answer in this data.

    Parameters
    ----------
    member_id: The member's stable id.
    variant_id: Optional — "strength", "conditioning", or "mobility".
        If None, all three variants are returned.

    Returns a dict with keys:
      - has_plan: bool
      - variants: list of variant summaries (or empty if no plan)
      - safety_filter_summary: summary of what was excluded + why
      - selected_variant_id: the coach's selected variant (or None)
    """
    from app.generator.store import get_current_plan

    output = get_current_plan(member_id)

    if output is None:
        return {
            "has_plan": False,
            "message": (
                "No workout plan has been generated yet for this member. "
                "Ask the coach to generate a plan first via the Generator panel."
            ),
            "member_id": member_id,
        }

    # Filter to the requested variant if specified
    variants_to_include = output.variants
    if variant_id is not None:
        variants_to_include = [
            v for v in output.variants if v.variant_id == variant_id
        ]
        if not variants_to_include:
            return {
                "has_plan": True,
                "error": (
                    f"Variant '{variant_id}' not found. "
                    f"Available variants: {[v.variant_id for v in output.variants]}"
                ),
            }

    # Serialize variants with full per-exercise rationale
    variant_summaries = []
    for v in variants_to_include:
        plan = v.plan
        all_exercises = plan.warmup + plan.main + plan.cooldown

        exercises_with_rationale = []
        for section_name, section in [
            ("warmup", plan.warmup),
            ("main", plan.main),
            ("cooldown", plan.cooldown),
        ]:
            for ex in section:
                exercises_with_rationale.append({
                    "section": section_name,
                    "order": ex.order,
                    "name": ex.name,
                    "exercise_id": ex.exercise_id,
                    "sets": ex.sets,
                    "reps": ex.reps,
                    "duration_seconds": ex.duration_seconds,
                    "rest_seconds": ex.rest_seconds,
                    "sequencing_role": ex.sequencing_role,
                    "rationale": ex.rationale,
                    "sequencing_rationale": ex.sequencing_rationale,
                })

        prov = v.provenance
        variant_summaries.append({
            "variant_id": v.variant_id,
            "label": v.label,
            "optimizes_for": v.optimizes_for,
            "stimulus": plan.stimulus,
            "target_adaptation": plan.target_adaptation,
            "design_rationale": plan.design_rationale,
            "sequence_logic": plan.sequence_logic,
            "total_minutes": plan.total_minutes,
            "exercise_count": len(all_exercises),
            "exercises": exercises_with_rationale,
            "provenance": {
                "generated_at": prov.generated_at.isoformat(),
                "prompt": prov.prompt,
                "healing_phase": prov.healing_phase,
                "load_tolerance_pct": prov.load_tolerance_pct,
                "stale_check_in": prov.stale_check_in,
            },
        })

    # Safety filter summary
    trace = output.trace
    filter_summary = {
        "safe_exercise_count": len(trace.safe),
        "removed_exercise_count": len(trace.removed),
        "removed_exercises": [
            {"name": ex.name, "id": ex.id, "reason": reason}
            for ex, reason in trace.removed[:10]  # cap at 10 for readability
        ],
        "load_tolerance_pct": trace.load_tolerance_pct,
        "stale_check_in": trace.stale_check_in,
    }

    return {
        "has_plan": True,
        "member_id": member_id,
        "selected_variant_id": output.selected_variant_id,
        "variants": variant_summaries,
        "safety_filter_summary": filter_summary,
        "variant_count": len(output.variants),
    }


# ---------------------------------------------------------------------------
# Phase 7.1 — additional grounding tools (R2/R3 gap-closing)
# ---------------------------------------------------------------------------


def lab_results(member_id: str) -> dict:
    """
    Return the member's latest lab results from the Member KG.

    Covers the blood panel (lipids, HbA1c, vitamin D, ferritin, CRP,
    and hormone panel for Mico) and DEXA body-composition scan.

    IMPORTANT: Only returns data that exists in the Member KG.  If a field
    is absent, it will be null.  Never invents values.

    Parameters
    ----------
    member_id: The member's stable id.
    """
    from app.data.loader import load_member_context
    try:
        member = load_member_context(member_id)
    except ValueError:
        return {"error": f"Member '{member_id}' not found"}

    from app.ontology.catalog import build_concept_catalog
    from app.graph.member_kg import MemberKG
    concepts = build_concept_catalog()
    mkg = MemberKG(member, concepts)

    labs = mkg.get_lab_results()

    blood = None
    if labs.blood_panel is not None:
        bp = labs.blood_panel
        blood = {
            "date": bp.date,
            "ldl_mg_dl": bp.ldl_mg_dl,
            "hdl_mg_dl": bp.hdl_mg_dl,
            "triglycerides_mg_dl": bp.triglycerides_mg_dl,
            "hba1c_pct": bp.hba1c_pct,
            "vitamin_d_ng_ml": bp.vitamin_d_ng_ml,
            "ferritin_ng_ml": bp.ferritin_ng_ml,
            "crp_mg_l": bp.crp_mg_l,
            # Hormone panel (present for Mico; null for Jordan)
            "testosterone_ng_dl": bp.testosterone_ng_dl,
            "free_testosterone_pg_ml": bp.free_testosterone_pg_ml,
            "cortisol_morning_mcg_dl": bp.cortisol_morning_mcg_dl,
            "shbg_nmol_l": bp.shbg_nmol_l,
            "dhea_s_mcg_dl": bp.dhea_s_mcg_dl,
            "igf1_ng_ml": bp.igf1_ng_ml,
        }

    dexa = None
    if labs.dexa_scan is not None:
        dx = labs.dexa_scan
        dexa = {
            "date": dx.date,
            "body_fat_pct": dx.body_fat_pct,
            "lean_mass_kg": dx.lean_mass_kg,
            "fat_mass_kg": dx.fat_mass_kg,
            "bone_density_z_score": dx.bone_density_z_score,
            "visceral_fat_cm2": dx.visceral_fat_cm2,
        }

    return {
        "member_id": member_id,
        "member_name": member.profile.name,
        "blood_panel": blood,
        "dexa_scan": dexa,
        "data_source": "Member KG — labs field from member context",
    }


def body_composition(member_id: str) -> dict:
    """
    Return the member's DEXA body-composition data.

    Focuses on the DEXA scan results: body fat %, lean mass, fat mass,
    bone density, and visceral fat.  Returns null fields if no DEXA is
    available — never invents values.

    Parameters
    ----------
    member_id: The member's stable id.
    """
    from app.data.loader import load_member_context
    try:
        member = load_member_context(member_id)
    except ValueError:
        return {"error": f"Member '{member_id}' not found"}

    from app.ontology.catalog import build_concept_catalog
    from app.graph.member_kg import MemberKG
    concepts = build_concept_catalog()
    mkg = MemberKG(member, concepts)

    labs = mkg.get_lab_results()
    biomarkers = mkg.get_biomarkers()

    dexa_data: dict = {"available": False}
    if labs.dexa_scan is not None:
        dx = labs.dexa_scan
        dexa_data = {
            "available": True,
            "date": dx.date,
            "body_fat_pct": dx.body_fat_pct,
            "lean_mass_kg": dx.lean_mass_kg,
            "fat_mass_kg": dx.fat_mass_kg,
            "bone_density_z_score": dx.bone_density_z_score,
            "visceral_fat_cm2": dx.visceral_fat_cm2,
        }

    weight_trend = [
        {"date": pt.date, "kg": pt.kg}
        for pt in biomarkers.weight_trend_kg
    ]

    return {
        "member_id": member_id,
        "member_name": member.profile.name,
        "dexa_scan": dexa_data,
        "weight_trend_kg": weight_trend,
        "current_weight_kg": member.profile.weight_kg,
        "data_source": "Member KG — labs.dexa_scan + biomarkers.weight_trend_kg",
    }


def workout_history(member_id: str, limit: int = 10) -> dict:
    """
    Return the member's recent logged workout sessions.

    Parameters
    ----------
    member_id: The member's stable id.
    limit: Maximum number of sessions to return (newest first, default 10).

    Returns a dict with keys: member_id, sessions (list), total_logged.
    """
    from app.data.loader import load_member_context
    try:
        member = load_member_context(member_id)
    except ValueError:
        return {"error": f"Member '{member_id}' not found"}

    from app.ontology.catalog import build_concept_catalog
    from app.graph.member_kg import MemberKG
    concepts = build_concept_catalog()
    mkg = MemberKG(member, concepts)

    sessions = mkg.get_workout_history()
    # Sort by date descending (most recent first)
    sessions_sorted = sorted(sessions, key=lambda s: s.date, reverse=True)
    sessions_limited = sessions_sorted[:limit]

    session_list = [
        {
            "date": s.date,
            "title": s.title,
            "planned": s.planned,
            "completed": s.completed,
            "duration_min": s.duration_min,
            "rpe": s.rpe,
            "exercises": s.exercises,
        }
        for s in sessions_limited
    ]

    return {
        "member_id": member_id,
        "member_name": member.profile.name,
        "sessions": session_list,
        "total_logged": len(sessions),
        "sessions_returned": len(session_list),
        "data_source": "Member KG — workout_history field",
    }


def goals_and_preferences(member_id: str) -> dict:
    """
    Return the member's goals and training preferences.

    Goals include text, priority, and target date.
    Preferences include session length, days per week, preferred days,
    dislikes, and any notes.

    Parameters
    ----------
    member_id: The member's stable id.
    """
    from app.data.loader import load_member_context
    try:
        member = load_member_context(member_id)
    except ValueError:
        return {"error": f"Member '{member_id}' not found"}

    from app.ontology.catalog import build_concept_catalog
    from app.graph.member_kg import MemberKG
    concepts = build_concept_catalog()
    mkg = MemberKG(member, concepts)

    goals = mkg.get_goals()
    prefs = mkg.get_preferences()

    goal_list = sorted(
        [
            {
                "id": g.id,
                "text": g.text,
                "priority": g.priority,
                "target_date": g.target_date,
            }
            for g in goals
        ],
        key=lambda g: g["priority"],
    )

    return {
        "member_id": member_id,
        "member_name": member.profile.name,
        "goals": goal_list,
        "preferences": {
            "preferred_session_minutes": prefs.preferred_session_minutes,
            "training_days_per_week": prefs.training_days_per_week,
            "preferred_days": prefs.preferred_days,
            "dislikes": prefs.dislikes,
            "notes": prefs.notes,
        },
        "data_source": "Member KG — goals + preferences fields",
    }


def chat_history_search(member_id: str, query: str = "") -> dict:
    """
    Return the member's seed chat history, optionally filtered by a query term.

    This retrieves the stored chat transcript from the Member KG.  Messages
    include sender (member/coach), timestamp, text, and any attachments.

    The optional query parameter filters messages that contain the query term
    (case-insensitive substring match on the message text).

    Parameters
    ----------
    member_id: The member's stable id.
    query: Optional search term to filter messages (default: return all).
    """
    from app.data.loader import load_member_context
    try:
        member = load_member_context(member_id)
    except ValueError:
        return {"error": f"Member '{member_id}' not found"}

    from app.ontology.catalog import build_concept_catalog
    from app.graph.member_kg import MemberKG
    concepts = build_concept_catalog()
    mkg = MemberKG(member, concepts)

    messages = mkg.get_chat_history()

    # Filter by query if provided
    if query.strip():
        q_lower = query.lower()
        messages = [m for m in messages if q_lower in m.text.lower()]

    # Sort oldest-first for readability
    messages_sorted = sorted(messages, key=lambda m: m.ts)

    msg_list = [
        {
            "ts": m.ts,
            "from": m.from_,
            "text": m.text,
            "attachments": [
                {"type": a.type, "caption": a.caption}
                for a in m.attachments
            ],
        }
        for m in messages_sorted
    ]

    return {
        "member_id": member_id,
        "member_name": member.profile.name,
        "query": query,
        "messages": msg_list,
        "total_messages": len(msg_list),
        "data_source": "Member KG — chat_history field",
    }


# ---------------------------------------------------------------------------
# System prompt (updated for anti-fabrication — Phase 7.1)
# ---------------------------------------------------------------------------


_COPILOT_SYSTEM_PROMPT = """\
You are an expert AI coaching assistant helping a coach manage their members.
You have access to tools that retrieve member data from the Member Knowledge Graph.

ANTI-FABRICATION RULE (CRITICAL):
  - You MUST call the appropriate tool to get data before answering.
  - You MUST NOT invent, guess, or extrapolate member data.
  - If the tool result does not contain the data needed to answer, say so
    explicitly: "The Member KG does not have data to support that answer."
  - Only cite values that appear verbatim in the tool response.

TOOL SELECTION GUIDE:
  - Adherence questions       → adherence_trend
  - Morning brief / churn     → morning_brief
  - Injury / healing phase    → injury_status
  - Sleep / biomarkers        → sleep_summary
  - Lab results / bloodwork   → lab_results
  - Body composition / DEXA   → body_composition
  - Past workouts             → workout_history
  - Goals / preferences       → goals_and_preferences
  - Chat history / messages   → chat_history_search
  - Workout plan questions    → current_workout_plan

WORKOUT PLAN: Call `current_workout_plan` whenever the coach mentions:
  - "this workout", "the plan", "the session", "these exercises"
  - "stimulus", "target adaptation", "what are we training for"
  - "why" in a workout context (why these exercises, why this order)
  - "order", "sequence", "why is X first/last"
  - "compare the variants", "which variant", "strength vs conditioning"
  - "what was filtered out", "excluded exercises", "safety"

When you have data from a tool, ground your answer in those exact values.
Do not elaborate beyond what the data says.

Keep answers concise and always cite the specific data you retrieved.
If the coach asks a follow-up, call tools again with the same member_id.
"""


# ---------------------------------------------------------------------------
# Conversation memory helpers (R2 — conversation memory + seed history)
# ---------------------------------------------------------------------------


def _seed_messages_for_member(member_id: str) -> list:
    """
    Build the initial conversation seed from a member's stored chat_history.

    Returns a list of LangChain message objects (HumanMessage / AIMessage)
    representing the prior coach–member chat transcript.  These are injected
    into the thread before the first user turn so the agent has historical
    context.

    Returns an empty list if the member has no chat history or the member
    cannot be loaded.
    """
    try:
        from app.data.loader import load_member_context
        from langchain_core.messages import AIMessage, HumanMessage

        member = load_member_context(member_id)
        messages: list = []
        for msg in sorted(member.chat_history, key=lambda m: m.ts):
            # Map "member" → human, "coach" → AI
            text = msg.text
            if msg.from_ == "member":
                messages.append(HumanMessage(content=text))
            else:
                messages.append(AIMessage(content=text))
        return messages
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


def create_copilot_agent(member_kg: "Any", llm: "Any") -> "Any | None":
    """
    Build a LangGraph ReAct agent wired to the Member KG tools.

    Phase 7.1 additions:
      - Compiled with a MemorySaver checkpointer for per-member conversation
        memory.  Invoke with config={"configurable": {"thread_id": member_id}}.
      - Additional grounding tools: lab_results, body_composition,
        workout_history, goals_and_preferences, chat_history_search.
      - Updated anti-fabrication system prompt.

    Parameters
    ----------
    member_kg:
        A MemberKG instance for the target member.  The agent's tools are
        bound to this member's data (via the member_id from the KG).
    llm:
        A LangChain BaseChatModel that supports tool calling.
        Pass None to get None back (callers handle the no-LLM case).

    Returns
    -------
    CompiledGraph or None
        A LangGraph compiled agent ready for .invoke() / .astream(), or
        None if llm is None (no API key).
    """
    if llm is None:
        return None

    try:
        from langchain_core.tools import tool as tool_decorator
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.prebuilt import create_react_agent

        # Wrap tool functions as LangChain tools with type annotations
        # so the LLM can call them by name.

        @tool_decorator
        def adherence_trend_tool(member_id: str, weeks: int = 4) -> dict:
            """Return the member's session adherence trend for the past N weeks."""
            return adherence_trend(member_id, weeks)

        @tool_decorator
        def morning_brief_tool(member_id: str) -> dict:
            """Return the coach's morning brief for the member (tasks + churn risk)."""
            return morning_brief(member_id)

        @tool_decorator
        def injury_status_tool(member_id: str) -> dict:
            """Return the member's active injuries with current healing phase and latest check-in."""
            return injury_status(member_id)

        @tool_decorator
        def sleep_summary_tool(member_id: str) -> dict:
            """Return the member's sleep data and biomarkers for the past 7 days."""
            return sleep_summary(member_id)

        @tool_decorator
        def current_workout_plan_tool(
            member_id: str, variant_id: str | None = None
        ) -> dict:
            """Read the most recently generated workout plan. Returns all 3 variants
            (or one if variant_id given) with stimulus, target_adaptation,
            design_rationale, per-exercise rationale, sequencing_rationale, and
            safety-filter provenance. Call this whenever the coach asks about the
            workout, exercises, stimulus, why exercises were chosen, or their order."""
            return current_workout_plan(member_id, variant_id)

        @tool_decorator
        def lab_results_tool(member_id: str) -> dict:
            """Return the member's latest lab results: blood panel (lipids, HbA1c,
            vitamin D, ferritin, CRP, hormone panel) and DEXA body-composition scan.
            Call this when asked about labs, bloodwork, testosterone, cortisol,
            cholesterol, or any clinical markers."""
            return lab_results(member_id)

        @tool_decorator
        def body_composition_tool(member_id: str) -> dict:
            """Return the member's DEXA body-composition data: body fat %, lean mass,
            fat mass, bone density, visceral fat, and weight trend.
            Call this when asked about body composition, DEXA, body fat, lean mass,
            or weight trend."""
            return body_composition(member_id)

        @tool_decorator
        def workout_history_tool(member_id: str, limit: int = 10) -> dict:
            """Return the member's recent logged workout sessions (date, title,
            duration, RPE, exercises performed). Call this when asked about past
            workouts, recent sessions, training history, or what they did last week."""
            return workout_history(member_id, limit)

        @tool_decorator
        def goals_and_preferences_tool(member_id: str) -> dict:
            """Return the member's goals (text, priority, target date) and training
            preferences (session length, training days, dislikes, notes).
            Call this when asked about goals, objectives, preferences, or dislikes."""
            return goals_and_preferences(member_id)

        @tool_decorator
        def chat_history_search_tool(member_id: str, query: str = "") -> dict:
            """Return the member's stored chat history transcript. Optionally filter
            by a search query (case-insensitive substring match on message text).
            Call this when asked about past conversations, what was said before,
            or to search for a specific topic in the chat history."""
            return chat_history_search(member_id, query)

        tools = [
            adherence_trend_tool,
            morning_brief_tool,
            injury_status_tool,
            sleep_summary_tool,
            current_workout_plan_tool,
            lab_results_tool,
            body_composition_tool,
            workout_history_tool,
            goals_and_preferences_tool,
            chat_history_search_tool,
        ]

        # Rename tools to cleaner names for the LLM
        adherence_trend_tool.name = "adherence_trend"
        morning_brief_tool.name = "morning_brief"
        injury_status_tool.name = "injury_status"
        sleep_summary_tool.name = "sleep_summary"
        current_workout_plan_tool.name = "current_workout_plan"
        lab_results_tool.name = "lab_results"
        body_composition_tool.name = "body_composition"
        workout_history_tool.name = "workout_history"
        goals_and_preferences_tool.name = "goals_and_preferences"
        chat_history_search_tool.name = "chat_history_search"

        # Compile with MemorySaver for per-member conversation memory (R2)
        checkpointer = MemorySaver()

        agent = create_react_agent(
            llm,
            tools=tools,
            prompt=_COPILOT_SYSTEM_PROMPT,
            checkpointer=checkpointer,
        )
        return agent

    except Exception:
        return None
