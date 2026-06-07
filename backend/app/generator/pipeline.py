"""
Generator Pipeline — Phase 6 (multi-member, 3 variants).

Orchestrates the deterministic pipeline:

  1. Load member context + constraints from MemberContext
  2. Apply conditional safety filter ONCE (today's injury state)
  3. LLM structures the SAME safe set into THREE labeled WorkoutVariants concurrently
  4. Build shared provenance + filter trace
  5. Return GeneratorOutput with variants + shared trace + optional selection

Safety contract:
  - The filter runs exactly once per generate call.
  - All three variants draw exercises only from the shared safe set.
  - The LLM never sees unsafe exercises.

Three variant profiles (always produced):
  "strength"    — Strength & Hypertrophy (load/intensity-biased, within load_tolerance_pct cap)
  "conditioning" — Conditioning & Metabolic (density, circuits, intervals, work:rest)
  "mobility"    — Mobility & Recovery (lower systemic load, ROM/recovery-biased, injury-safe primers)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from langchain_core.language_models import BaseChatModel

from app.graph.conditional_filter import ConditionalFilterTrace, conditional_safety_filter
from app.graph.movement_kg import MovementKG
from app.models.exercise import Exercise
from app.models.injury import Injury, InjuryState
from app.models.member import MemberContext
from app.models.plan import WorkoutPlan


# ---------------------------------------------------------------------------
# Variant registry
# ---------------------------------------------------------------------------

# Each tuple: (variant_id, label, optimizes_for)
VARIANT_PROFILES: list[tuple[str, str, str]] = [
    (
        "strength",
        "Strength & Hypertrophy",
        "load/intensity-biased strength with hypertrophy stimulus",
    ),
    (
        "conditioning",
        "Conditioning & Metabolic",
        "density/metabolic work via circuits, intervals, and work:rest structure",
    ),
    (
        "mobility",
        "Mobility & Recovery",
        "lower systemic load, ROM-biased recovery with injury-safe primers",
    ),
]


# ---------------------------------------------------------------------------
# Input / Output types
# ---------------------------------------------------------------------------


@dataclass
class GeneratorInput:
    """
    Everything the generator needs to produce a plan.

    Attributes
    ----------
    prompt:
        Free-text session intent from the coach, e.g. "lower body strength".
    time_window_minutes:
        Available session time in minutes.
    member_id:
        The member's id — used to look up context and persist the plan.
    """

    prompt: str
    time_window_minutes: int
    member_id: str


@dataclass
class Provenance:
    """
    Lightweight PROV-O-shaped record capturing what drove the plan.

    Phase 12 will extend this to a full PROV-O JSON document; here we
    capture the essential fields the Copilot needs to answer "why" questions.

    Attributes
    ----------
    generated_at:
        UTC timestamp when the plan was produced.
    prompt:
        The coach's original prompt.
    time_window_minutes:
        The requested session window.
    injury_state_used:
        The InjuryState snapshot that drove dynamic filtering, or None.
    healing_phase:
        The active healing phase string (e.g. "remodeling").
    load_tolerance_pct:
        The effective load tolerance cap applied (0.0-1.0).
    stale_check_in:
        True if the injury state was from a previous day.
    exercises_filtered_out:
        List of (exercise_name, reason) for every excluded exercise.
    equipment_available:
        Equipment set used for filtering.
    """

    generated_at: datetime
    prompt: str
    time_window_minutes: int
    injury_state_used: InjuryState | None = None
    healing_phase: str | None = None
    load_tolerance_pct: float = 1.0
    stale_check_in: bool = False
    exercises_filtered_out: list[dict] = field(default_factory=list)
    equipment_available: list[str] = field(default_factory=list)


@dataclass
class WorkoutVariant:
    """
    One of three labeled workout variants produced from the shared safe set.

    Attributes
    ----------
    variant_id:
        Stable machine-readable id: "strength" | "conditioning" | "mobility".
    label:
        Human-readable label for the card header, e.g. "Strength & Hypertrophy".
    optimizes_for:
        One-line stimulus/modality tag, e.g. "load/intensity-biased strength".
    plan:
        The structured WorkoutPlan — carries its OWN distinct stimulus /
        target_adaptation / design_rationale fields.
    provenance:
        Per-variant provenance record.
    """

    variant_id: str
    label: str
    optimizes_for: str
    plan: WorkoutPlan
    provenance: Provenance


@dataclass
class GeneratorOutput:
    """
    Complete output from the generator pipeline.

    Attributes
    ----------
    variants:
        Exactly 3 WorkoutVariants — strength, conditioning, mobility.
        All drawn from the SAME shared safe candidate set.
    trace:
        The single shared ConditionalFilterTrace (filter ran once).
    selected_variant_id:
        Set when the coach explicitly picks a variant via /api/generate/select.
        None until a selection is made.
    """

    variants: list[WorkoutVariant]
    trace: ConditionalFilterTrace
    selected_variant_id: str | None = None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


async def generate_workout(
    input: GeneratorInput,
    kg: MovementKG,
    member: MemberContext,
    llm: BaseChatModel,
) -> GeneratorOutput:
    """
    Run the full generator pipeline and return a GeneratorOutput with 3 variants.

    Safety contract: the conditional safety filter runs ONCE. The resulting
    safe set is then structured three ways (strength / conditioning / mobility)
    by the LLM, concurrently via asyncio.gather.

    Parameters
    ----------
    input:
        The GeneratorInput with prompt, time window, and member id.
    kg:
        A pre-built MovementKG instance (shared / singleton).
    member:
        The loaded MemberContext for the member.
    llm:
        A LangChain BaseChatModel for plan structuring.

    Returns
    -------
    GeneratorOutput with 3 variants, shared filter trace, and no selection yet.
    """
    started_at = datetime.now(tz=timezone.utc)

    # ------------------------------------------------------------------
    # 1. Extract member constraints
    # ------------------------------------------------------------------
    available_equipment: set[str] = set(member.equipment_available)
    dislikes: set[str] = set(member.preferences.dislikes)

    # ------------------------------------------------------------------
    # 2. Get all candidate exercises from KG
    # ------------------------------------------------------------------
    candidates: list[Exercise] = kg.all_exercises()

    # ------------------------------------------------------------------
    # 3. Apply conditional safety filter ONCE using today's injury state
    # ------------------------------------------------------------------
    from app.api.routes.injury import _load_injury  # lazy import to avoid circular

    injury: Injury | None = None
    trace: ConditionalFilterTrace | None = None

    if member.injuries:
        first_raw = member.injuries[0]
        try:
            # Promote and merge in-memory check-in states
            injury = _load_injury(member.profile.id, first_raw.id)
        except Exception:
            # Fall back to promoting the raw injury without in-memory states
            from app.api.routes.injury import _promote_injury
            injury = _promote_injury(first_raw, member.profile.id)

    if injury is not None:
        trace = conditional_safety_filter(
            candidates=candidates,
            injury=injury,
            available_equipment=available_equipment,
            excluded_ids=set(),
            dislikes=dislikes,
            kg=kg,
        )
    else:
        # No injury: run base safety filter (equipment + dislikes only)
        from app.graph.safety_filter import FilterTrace, safety_filter
        base_trace = safety_filter(
            candidates=candidates,
            injured_joints=[],
            available_equipment=available_equipment,
            excluded_ids=set(),
            dislikes=dislikes,
            kg=kg,
        )
        # Wrap in a ConditionalFilterTrace for uniform downstream handling
        trace = ConditionalFilterTrace(
            safe=base_trace.safe,
            removed=base_trace.removed,
            substitutions=base_trace.substitutions,
            injury_state_used=None,
            phase_restrictions_applied={},
            load_tolerance_pct=1.0,
            stale_check_in=False,
        )

    safe_exercises = trace.safe

    # ------------------------------------------------------------------
    # 4. LLM structures the safe set into 3 variants concurrently
    # ------------------------------------------------------------------
    from app.generator.llm import structure_plan

    async def _structure_variant(
        variant_id: str,
        label: str,
        optimizes_for: str,
    ) -> WorkoutVariant:
        """Structure one variant using asyncio thread executor for blocking LLM call."""
        # Build a variant-specific intent string
        variant_intent = _build_variant_intent(
            coach_prompt=input.prompt,
            variant_id=variant_id,
            label=label,
            optimizes_for=optimizes_for,
        )

        loop = asyncio.get_event_loop()
        plan: WorkoutPlan = await loop.run_in_executor(
            None,
            lambda: structure_plan(
                safe_exercises=safe_exercises,
                intent=variant_intent,
                time_minutes=input.time_window_minutes,
                load_tolerance_pct=trace.load_tolerance_pct,
                llm=llm,
            ),
        )

        prov = Provenance(
            generated_at=started_at,
            prompt=input.prompt,
            time_window_minutes=input.time_window_minutes,
            injury_state_used=trace.injury_state_used,
            healing_phase=(
                injury.computed_phase().value if injury is not None else None
            ),
            load_tolerance_pct=trace.load_tolerance_pct,
            stale_check_in=trace.stale_check_in,
            exercises_filtered_out=[
                {"name": ex.name, "id": ex.id, "reason": reason}
                for ex, reason in trace.removed
            ],
            equipment_available=sorted(available_equipment),
        )

        return WorkoutVariant(
            variant_id=variant_id,
            label=label,
            optimizes_for=optimizes_for,
            plan=plan,
            provenance=prov,
        )

    # Run all three variant structuring calls concurrently
    variant_tasks = [
        _structure_variant(vid, label, opt_for)
        for vid, label, opt_for in VARIANT_PROFILES
    ]
    variants: list[WorkoutVariant] = list(await asyncio.gather(*variant_tasks))

    return GeneratorOutput(
        variants=variants,
        trace=trace,
        selected_variant_id=None,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_variant_intent(
    coach_prompt: str,
    variant_id: str,
    label: str,
    optimizes_for: str,
) -> str:
    """
    Build a variant-specific intent string for the LLM structuring call.

    Combines the coach's original prompt with a clear directive for the
    variant's optimization goal.
    """
    variant_directives = {
        "strength": (
            "Focus on STRENGTH & HYPERTROPHY: prioritise compound lifts with "
            "progressive overload, moderate-to-heavy loads (within load tolerance), "
            "longer rest periods (90-180s), and 3-5 sets per exercise. "
            "Stimulus = maximal mechanical tension. "
            "Design for adaptation: muscle strength and size."
        ),
        "conditioning": (
            "Focus on CONDITIONING & METABOLIC: prioritise density and work capacity. "
            "Use circuit structures, supersets, or interval formats (e.g. EMOM, AMRAP). "
            "Keep rest periods short (20-45s between exercises). "
            "Stimulus = metabolic stress + cardiovascular demand. "
            "Design for adaptation: aerobic base, work capacity, fat oxidation."
        ),
        "mobility": (
            "Focus on MOBILITY & RECOVERY: prioritise ROM development, injury-safe "
            "activation primers, and lower systemic load. "
            "Include stretching, controlled-articular rotations, and low-load "
            "stability work. Keep intensity low (RPE 4-6). "
            "Stimulus = tissue quality + joint health. "
            "Design for adaptation: mobility, flexibility, active recovery."
        ),
    }

    directive = variant_directives.get(variant_id, f"Focus on {label}: {optimizes_for}.")

    return (
        f"Coach prompt: {coach_prompt}\n\n"
        f"Variant: {label}\n"
        f"{directive}"
    )
