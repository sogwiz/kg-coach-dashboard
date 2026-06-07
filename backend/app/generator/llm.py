"""
LLM structuring layer — Phase 6.

Wraps Claude (claude-haiku-3) via LangChain with `with_structured_output`
so the model emits a valid WorkoutPlan JSON directly.

The LLM only sees SAFE exercises (post-filter); it never receives
contraindicated exercises.  Its job is purely to order the safe set into
warmup / main / cooldown sections and write per-exercise + session-level
rationale fields.

If ANTHROPIC_API_KEY is not set, get_structuring_llm() raises a clear
RuntimeError so callers can skip gracefully in test environments.
"""

from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel

from app.models.exercise import Exercise
from app.models.plan import PlannedExercise, WorkoutPlan

# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

_MODEL_NAME = "claude-haiku-4-5"
_TEMPERATURE = 0.3


def get_structuring_llm() -> BaseChatModel:
    """
    Return a LangChain ChatAnthropic model configured for workout structuring.

    Raises
    ------
    RuntimeError
        If ANTHROPIC_API_KEY is not set in the environment.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set.  "
            "Export it before starting the server or running LLM-dependent tests."
        )

    from langchain_anthropic import ChatAnthropic  # deferred to avoid import cost

    return ChatAnthropic(  # type: ignore[call-arg]
        model=_MODEL_NAME,
        temperature=_TEMPERATURE,
        api_key=api_key,
    )


# ---------------------------------------------------------------------------
# Structuring prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert coach assistant that structures safe exercise lists into
complete workout plans.

You will receive:
- A set of SAFE exercises (already filtered; do NOT question the list)
- The coach's intent / prompt
- The session time window in minutes
- The member's current load tolerance (0-100 %)

Your job:
1. Organise the exercises into warmup / main / cooldown sections appropriate
   for the intent and time window.
2. Assign realistic sets, reps (or duration_seconds), and rest periods.
3. Cap loading relative to load_tolerance_pct (e.g. 70 % tolerance → moderate
   sets/reps, avoid near-maximal efforts; note it in design_rationale).
4. Write a one-sentence rationale for each exercise explaining its role.
5. Fill in the three session-level fields:
   - stimulus: the primary training stimulus in plain language
   - target_adaptation: the physiological adaptation targeted
   - design_rationale: a paragraph explaining how the prompt, load tolerance,
     and time window shaped the overall design

Return ONLY the structured JSON matching the WorkoutPlan schema.
Do not invent exercises — use only the exercises from the provided list.
"""

_USER_TEMPLATE = """\
Coach prompt: {intent}
Session time: {time_minutes} minutes
Load tolerance: {load_tolerance_pct:.0%}

Available safe exercises:
{exercise_list}
"""


def structure_plan(
    safe_exercises: list[Exercise],
    intent: str,
    time_minutes: int,
    load_tolerance_pct: float,
    llm: BaseChatModel,
) -> WorkoutPlan:
    """
    Ask the LLM to structure safe exercises into a WorkoutPlan.

    Parameters
    ----------
    safe_exercises:
        Exercises that passed the conditional safety filter.
    intent:
        The coach's free-text prompt / session goal.
    time_minutes:
        Available session window in minutes.
    load_tolerance_pct:
        Effective load tolerance from the conditional filter (0.0-1.0).
    llm:
        A LangChain BaseChatModel (must support with_structured_output).

    Returns
    -------
    WorkoutPlan
        The structured plan with per-exercise and session-level fields.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    # Build the exercise list for the prompt
    exercise_lines: list[str] = []
    for ex in safe_exercises:
        line = (
            f"- id={ex.id!r} name={ex.name!r} "
            f"patterns={ex.movement_patterns!r} "
            f"muscles={ex.muscle_groups!r} "
            f"equipment={ex.equipment_required!r} "
            f"is_reps={ex.is_reps} is_duration={ex.is_duration}"
        )
        exercise_lines.append(line)

    user_content = _USER_TEMPLATE.format(
        intent=intent,
        time_minutes=time_minutes,
        load_tolerance_pct=load_tolerance_pct,
        exercise_list="\n".join(exercise_lines) if exercise_lines else "(none)",
    )

    structured_llm = llm.with_structured_output(WorkoutPlan)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    plan: WorkoutPlan = structured_llm.invoke(messages)  # type: ignore[assignment]
    return plan
