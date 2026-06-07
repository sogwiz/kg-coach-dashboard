"""
Narrow LLM narration for the hybrid engine.

Given an ALREADY-ASSEMBLED plan (assembler.py), the LLM writes ONLY the four
session-level prose fields — stimulus, target_adaptation, design_rationale,
sequence_logic. This is a tiny output (~250-350 tokens) vs. the ~2,000 tokens
of full-plan structuring, so it returns in a few seconds. The per-exercise
rationale and the structure were already produced deterministically.

Falls back to a templated narration when no LLM is configured, so the hybrid
engine works fully offline.
"""

from __future__ import annotations

import asyncio

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app.models.plan import WorkoutPlan


class PlanNarration(BaseModel):
    """The four session-level prose fields the LLM writes for the hybrid plan."""

    stimulus: str = Field(default="", description="Primary training stimulus, <= 12 words.")
    target_adaptation: str = Field(default="", description="Physiological adaptation targeted, <= 12 words.")
    design_rationale: str = Field(
        default="",
        description="3-4 sentence paragraph: how the intent, injury/constraints, load tolerance, and time shaped this design.",
    )
    sequence_logic: str = Field(default="", description="1-2 sentences on the ordering strategy.")


_SYS = """\
You are an expert coach assistant. You are given an ALREADY-ASSEMBLED workout
(sections, exercises, sets/reps/rest). Write ONLY the session-level explanation
fields. Do NOT change the plan, add exercises, or question the selection.

- design_rationale: a clear 3-4 sentence PARAGRAPH explaining how the coach's
  intent, the member's injury / constraints, the load-tolerance cap, and the
  time window shaped THIS design and what was prioritized. Ground it in the
  actual exercises and rep/rest schemes shown.
- sequence_logic: 1-2 sentences on the ordering principle (compounds while
  fresh, injury-protective activation early, conditioning late, cooldown last).
- stimulus and target_adaptation: <= 12 words each.

Be concrete and specific to the given plan. Return only the structured fields.
"""


def _plan_summary(plan: WorkoutPlan) -> str:
    def scheme(e) -> str:
        return f"{e.sets}x{e.reps}" if e.reps is not None else f"{e.sets}x{e.duration_seconds}s"

    def sec(name: str, items) -> str:
        body = ", ".join(f"{e.name} {scheme(e)} (rest {e.rest_seconds}s)" for e in items)
        return f"{name}: {body or '(none)'}"

    return "\n".join(
        [sec("Warmup", plan.warmup), sec("Main", plan.main), sec("Cooldown", plan.cooldown)]
    )


async def narrate_plan(
    plan: WorkoutPlan,
    intent: str,
    injury_context: str,
    llm: BaseChatModel,
    run_config: dict | None = None,
) -> PlanNarration:
    """Ask the LLM to write only the session-level prose for an assembled plan."""
    from langchain_core.messages import HumanMessage, SystemMessage

    structured = llm.with_structured_output(PlanNarration)
    user = (
        f"Coach intent: {intent}\n"
        f"Member injury / constraints: {injury_context}\n"
        f"Assembled plan:\n{_plan_summary(plan)}"
    )
    messages = [SystemMessage(content=_SYS), HumanMessage(content=user)]
    invoke_kwargs: dict = {"config": run_config} if run_config else {}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: structured.invoke(messages, **invoke_kwargs)
    )


def templated_narration(plan: WorkoutPlan, intent: str) -> PlanNarration:
    """Deterministic fallback narration (no LLM)."""
    d = plan.stimulus_distribution
    top = max(
        [("strength", d.strength), ("conditioning", d.conditioning), ("mobility", d.mobility)],
        key=lambda x: x[1],
    )[0]
    stim = {
        "strength": "strength & loading",
        "conditioning": "conditioning & work capacity",
        "mobility": "mobility & recovery",
    }[top]
    adapt = {
        "strength": "strength and tissue capacity",
        "conditioning": "work capacity and metabolic conditioning",
        "mobility": "range of motion and active recovery",
    }[top]
    return PlanNarration(
        stimulus=stim,
        target_adaptation=adapt,
        design_rationale=(
            f"Assembled deterministically from the safe exercise pool for "
            f"\"{intent}\". Anything contraindicated for the member's injury was "
            f"filtered out before assembly, so the selection is safe by "
            f"construction. Set/rep/rest schemes follow the inferred training "
            f"mode, and the structure spreads the time window across warmup, "
            f"main, and cooldown."
        ),
        sequence_logic=(
            "Activation and mobility open the session, compounds run while you're "
            "fresh, conditioning is placed late, and a cooldown closes it."
        ),
    )
