"""
Copilot agent — Phase 7.

A LangGraph tool-calling (ReAct) agent that answers coach questions about a
member's context by calling tools backed by the Member KG.

Tools
-----
  adherence_trend(member_id, weeks=4)
      Return the member's adherence trend for the past N weeks.

  morning_brief(member_id)
      Return the coach's morning brief for the member (tasks + churn risk).

  injury_status(member_id)
      Return the member's active injuries with current healing phase.

  sleep_summary(member_id)
      Return the member's sleep data for the past 7 days.

  current_workout_plan(member_id, variant_id=None)
      Read the Phase 6 generator store and return all 3 variants (or one)
      with their stimulus/target_adaptation/design_rationale, per-exercise
      rationale + sequencing_rationale, and the safety-filter provenance.
      Returns a "no plan generated yet" marker when the store is empty.

System prompt instructs the agent to call current_workout_plan whenever the
coach references "this workout", "the plan", "these exercises", "stimulus",
"why" in a workout context, or "order".

LLM setup
---------
Uses the same provider-agnostic approach as the generator (ChatAnthropic via
get_copilot_llm()).  Degrades gracefully / skips when no ANTHROPIC_API_KEY —
the agent constructor returns None and callers check for that.

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

    Uses claude-haiku-4-5 (same as the generator — fast, cheap, tool-capable).

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
# System prompt
# ---------------------------------------------------------------------------


_COPILOT_SYSTEM_PROMPT = """\
You are an expert AI coaching assistant helping a coach manage their members.
You have access to tools that retrieve member data. Always call the appropriate
tool to get data before answering — do not invent or guess data.

CRITICAL: Call `current_workout_plan` whenever the coach mentions:
  - "this workout", "the plan", "the session", "these exercises"
  - "stimulus", "target adaptation", "what are we training for"
  - "why" in a workout context (why these exercises, why this order, why this design)
  - "order", "sequence", "why is X first/last"
  - "compare the variants", "which variant", "strength vs conditioning"
  - "what was filtered out", "what exercises were excluded", "safety"

When you have workout plan data, ground your answer in the returned:
  - stimulus / target_adaptation / design_rationale  (session-level why)
  - exercises[].rationale  (per-exercise selection why)
  - exercises[].sequencing_rationale  (per-exercise ordering why)
  - sequence_logic  (overall ordering narrative)
  - safety_filter_summary  (what was excluded and why)

Do not invent reasoning — cite the rationale fields from the tool response.

For adherence questions, call `adherence_trend`.
For morning brief or churn risk, call `morning_brief`.
For injury questions, call `injury_status`.
For sleep or biomarker questions, call `sleep_summary`.

Keep answers concise and cite the specific data you retrieved. If the coach
asks a follow-up, call tools again with the same member_id.
"""


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


def create_copilot_agent(member_kg: "Any", llm: "Any") -> "Any | None":
    """
    Build a LangGraph ReAct agent wired to the Member KG tools.

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

        tools = [
            adherence_trend_tool,
            morning_brief_tool,
            injury_status_tool,
            sleep_summary_tool,
            current_workout_plan_tool,
        ]

        # Rename tools to cleaner names for the LLM
        adherence_trend_tool.name = "adherence_trend"
        morning_brief_tool.name = "morning_brief"
        injury_status_tool.name = "injury_status"
        sleep_summary_tool.name = "sleep_summary"
        current_workout_plan_tool.name = "current_workout_plan"

        agent = create_react_agent(
            llm,
            tools=tools,
            prompt=_COPILOT_SYSTEM_PROMPT,
        )
        return agent

    except Exception:
        return None
