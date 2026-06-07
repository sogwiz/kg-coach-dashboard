"""
LLM structuring layer — Phase 6 (updated with sequencing fields).

Wraps Claude (claude-haiku-4-5) via LangChain with `with_structured_output`
so the model emits a valid WorkoutPlan JSON directly.

The LLM only sees SAFE exercises (post-filter); it never receives
contraindicated exercises.  Its job is to:
  1. Organise the safe set into warmup / main / cooldown sections.
  2. Assign sets, reps / duration, and rest periods.
  3. Write per-exercise selection rationale (why THIS exercise).
  4. Write per-exercise sequencing rationale (why HERE, before/after that one).
  5. Assign a sequencing_role to every exercise.
  6. Write a session-level sequence_logic narrative (overall ordering strategy).
  7. Fill the session-level stimulus / target_adaptation / design_rationale.

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
complete, well-sequenced workout plans.

You will receive:
- A set of SAFE exercises (already filtered; do NOT question the list)
- The coach's intent / prompt
- The session time window in minutes
- The member's current load tolerance (0-100 %)
- The member's active injury (joint + injury type), when present

Your job:
1. Organise the exercises into warmup / main / cooldown sections appropriate
   for the intent and time window.

2. ORDER exercises within each section using real training principles:
   - Warmup: mobility drills → activation → injury-protective primers
     (e.g. banded hip thrusts BEFORE squats to pre-activate glutes and spare
     the lumbar spine; clamshells BEFORE lunges to protect the knee).
   - Main: CNS-intensive compounds (squats, deadlifts, presses) FIRST, then
     accessory/isolation work, then conditioning / metabolic work last.
   - Cooldown: static stretches and parasympathetic down-regulation last.
   - If the member has a joint injury, place injury-protective activation
     primers immediately before the compound movement that stresses that joint.

3. Assign each exercise an `order` value (1-based integer, unique and
   consecutive within its section — warmup exercises are numbered 1,2,3,...
   independently from main section exercises which are also 1,2,3,...).

4. Assign each exercise a `sequencing_role` from:
   "activation" | "primer" | "compound" | "accessory" | "conditioning" | "cooldown"
   - activation: mobility / neuromuscular wake-up early in warmup
   - primer: injury-protective pre-activation (e.g. glute bridge before squat)
   - compound: CNS-intensive multi-joint strength movement
   - accessory: single-joint / isolation work after compounds
   - conditioning: metabolic / density work (circuits, intervals)
   - cooldown: stretching or parasympathetic recovery

5. Write a `sequencing_rationale` for EVERY exercise (1-2 sentences) that
   explains WHY this exercise sits at this position — its relationship to the
   exercise immediately before and/or after it in the section.
   Examples:
   - "Placed before the squat: banded hip thrusts pre-activate the glutes so
     they fire correctly under load, sparing the lumbar spine."
   - "Follows the compound squat while the CNS is still fresh; heavier load
     here capitalises on the primed posterior chain."
   - "Final warmup exercise — bridges from the activation series into the main
     lifting block without taxing the injured knee."

6. Write a `rationale` for EVERY exercise (1 sentence) explaining why THIS
   exercise was selected and how it serves the session's intent.

7. Assign realistic sets, reps (or duration_seconds), and rest periods.
   Cap loading relative to load_tolerance_pct (e.g. 70 % tolerance →
   moderate sets/reps, avoid near-maximal efforts).

8. Write the four session-level fields:
   - stimulus: the primary training stimulus in plain language
   - target_adaptation: the physiological adaptation targeted
   - design_rationale: a paragraph explaining how the prompt, load tolerance,
     injury state, and time window shaped the overall design
   - sequence_logic: a one-paragraph narrative of the OVERALL ordering
     strategy for the session — explain why exercises appear in this order,
     cite training principles (CNS intensity, fatigue management, injury
     protection), and tie the sequence to the member's injury where relevant.
     Example: "The session opens with hip mobility and glute activation to
     pre-load the posterior chain before any spinal loading, directly
     protecting Mico's lumbar spine. Compounds follow while the CNS is fresh,
     with accessories trailing to manage cumulative fatigue. Conditioning
     work is placed last to avoid pre-fatiguing the prime movers needed for
     strength sets."

Return ONLY the structured JSON matching the WorkoutPlan schema.
Do not invent exercises — use only the exercises from the provided list.
Populate ALL fields: order, sequencing_role, sequencing_rationale, rationale,
sequence_logic, stimulus, target_adaptation, design_rationale.
"""

_USER_TEMPLATE = """\
Coach prompt: {intent}
Session time: {time_minutes} minutes
Load tolerance: {load_tolerance_pct:.0%}
Member injury context: {injury_context}

Available safe exercises:
{exercise_list}
"""


def structure_plan(
    safe_exercises: list[Exercise],
    intent: str,
    time_minutes: int,
    load_tolerance_pct: float,
    llm: BaseChatModel,
    injury_context: str = "none",
    run_config: dict | None = None,
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
    injury_context:
        Plain-language description of the member's active injury for the
        prompt, e.g. "left knee PFPS (pain on flexion), remodeling phase".
        Defaults to "none" when no injury is present.
    run_config:
        Optional RunnableConfig for LangSmith tracing (from tracing_config()).
        When None, the call runs without tracing metadata.

    Returns
    -------
    WorkoutPlan
        The structured plan with per-exercise and session-level fields,
        including order, sequencing_role, sequencing_rationale, and
        sequence_logic.
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
        injury_context=injury_context,
        exercise_list="\n".join(exercise_lines) if exercise_lines else "(none)",
    )

    structured_llm = llm.with_structured_output(WorkoutPlan)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    invoke_kwargs: dict = {}
    if run_config:
        invoke_kwargs["config"] = run_config

    plan: WorkoutPlan = structured_llm.invoke(messages, **invoke_kwargs)  # type: ignore[assignment]
    return plan
