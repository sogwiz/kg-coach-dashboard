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
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, AsyncIterator

from langchain_core.language_models import BaseChatModel

from app.graph.conditional_filter import ConditionalFilterTrace, conditional_safety_filter
from app.graph.movement_kg import MovementKG
from app.models.exercise import Exercise
from app.models.injury import Injury, InjuryState
from app.models.member import MemberContext
from app.models.plan import WorkoutPlan

if TYPE_CHECKING:
    from app.observability.decision_trace import DecisionStep


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
    # Regenerate support: when set, the LLM is asked to produce a fresh
    # variation that differs from this summary of the previously generated plan.
    prior_plan_summary: str | None = None
    # Optional natural-language tweak applied on regenerate (e.g. "more posterior
    # chain", "swap in kettlebells"). Appended to the structuring intent.
    adjustment: str | None = None
    # Generation engine: "hybrid" (deterministic assembler + narrow LLM
    # narration — fast, default) or "llm" (LLM structures the whole plan).
    engine: str = "hybrid"


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
    decision_trace:
        Ordered list of DecisionStep records capturing every deterministic and
        LLM step in the pipeline (Phase 7 observability).  None until the
        generator builds it after the filter + structuring run.
    prov_documents:
        Phase 12: per-variant PROV-O provenance documents (one per variant).
        Keyed by variant_id.  None until the generator builds them.
        This is ADDITIVE — the variants[] contract is unchanged.
    """

    variants: list[WorkoutVariant]
    trace: ConditionalFilterTrace
    selected_variant_id: str | None = None
    decision_trace: "list[DecisionStep] | None" = None
    prov_documents: "dict[str, Any] | None" = None


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

    _t_filter = time.perf_counter()
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
    filter_ms = (time.perf_counter() - _t_filter) * 1000.0

    # ------------------------------------------------------------------
    # 4. LLM structures the safe set into ONE plan
    #
    # Single variant: the coach's free-text prompt already determines the
    # modality, so we make ONE structuring call (not three). The plan reports
    # its own strength/conditioning/mobility stimulus distribution, which the
    # UI renders as thermometer gauges.
    # ------------------------------------------------------------------
    from app.generator.llm import structure_plan
    from app.observability.tracing import tracing_config

    # Build a plain-language injury context string for the LLM prompt
    injury_context_str: str = "none"
    if injury is not None:
        phase_val = injury.computed_phase().value
        state = injury.current_state()
        if state is not None:
            pain_str = ", ".join(state.pain_on) if state.pain_on else "none"
            injury_context_str = (
                f"{injury.diagnosis} at {injury.joint} "
                f"({phase_val} phase, pain on: {pain_str}, "
                f"load tolerance: {state.load_tolerance_pct:.0%})"
            )
        else:
            injury_context_str = f"{injury.diagnosis} at {injury.joint} ({phase_val} phase)"

    # Compose the structuring intent: coach prompt + optional regenerate context.
    intent = input.prompt
    if input.prior_plan_summary:
        intent = (
            f"{input.prompt}\n\n"
            "REGENERATE — produce a FRESH variation that is meaningfully different "
            "from the previous session below: vary exercise selection, ordering, "
            "and set/rep schemes while honoring the same intent, time window, and "
            "safety constraints.\n"
            f"Previous session:\n{input.prior_plan_summary}"
        )
    if input.adjustment:
        intent = f"{intent}\n\nCoach adjustment: {input.adjustment}"

    run_cfg = tracing_config(
        "structure_plan",
        member_id=input.member_id,
        variant_id="primary",
        prompt=input.prompt,
    )

    _t_llm = time.perf_counter()
    loop = asyncio.get_event_loop()

    if input.engine == "hybrid":
        # HYBRID: deterministic assembler builds the structure + per-exercise
        # rationale + stimulus distribution (instant); a narrow LLM call writes
        # only the four session-level prose fields. Falls back to a templated
        # narration when no LLM is available.
        from app.generator.assembler import assemble_plan
        from app.generator.narrate import narrate_plan, templated_narration

        plan = assemble_plan(
            safe_exercises=safe_exercises,
            prompt=intent,
            time_minutes=input.time_window_minutes,
            load_tolerance_pct=trace.load_tolerance_pct,
            injury=injury,
        )
        try:
            narration = await narrate_plan(
                plan, intent, injury_context_str, llm, run_cfg
            )
        except Exception:
            narration = templated_narration(plan, intent)
        plan.stimulus = narration.stimulus or plan.stimulus
        plan.target_adaptation = narration.target_adaptation or plan.target_adaptation
        plan.design_rationale = narration.design_rationale or plan.design_rationale
        plan.sequence_logic = narration.sequence_logic or plan.sequence_logic
    else:
        # LLM: the model structures the entire plan (richer, slower).
        plan = await loop.run_in_executor(
            None,
            lambda: structure_plan(
                safe_exercises=safe_exercises,
                intent=intent,
                time_minutes=input.time_window_minutes,
                load_tolerance_pct=trace.load_tolerance_pct,
                llm=llm,
                injury_context=injury_context_str,
                run_config=run_cfg,
            ),
        )

    llm_ms = (time.perf_counter() - _t_llm) * 1000.0

    prov = Provenance(
        generated_at=started_at,
        prompt=input.prompt,
        time_window_minutes=input.time_window_minutes,
        injury_state_used=trace.injury_state_used,
        healing_phase=(injury.computed_phase().value if injury is not None else None),
        load_tolerance_pct=trace.load_tolerance_pct,
        stale_check_in=trace.stale_check_in,
        exercises_filtered_out=[
            {"name": ex.name, "id": ex.id, "reason": reason}
            for ex, reason in trace.removed
        ],
        equipment_available=sorted(available_equipment),
    )

    variant = WorkoutVariant(
        variant_id="primary",
        label="Session Plan",
        optimizes_for=(plan.stimulus or input.prompt),
        plan=plan,
        provenance=prov,
    )
    variants: list[WorkoutVariant] = [variant]

    # ------------------------------------------------------------------
    # 5. Build the in-app decision trace (Phase 7 observability)
    # ------------------------------------------------------------------
    from app.observability.decision_trace import build_decision_trace

    # Collect the movement type exclusions from the filter trace
    excluded_mvt_types: set[str] | None = None
    injured_node_ids_set: set[str] | None = None
    injury_joint_slug: str | None = None

    if injury is not None:
        injury_joint_slug = injury.joint
        injured_node_ids_set = kg.descendants_by_part_of(injury.joint)
        from app.models.healing import PHASE_RESTRICTIONS
        phase_restrictions = PHASE_RESTRICTIONS[injury.computed_phase()]
        excluded_mvt_types = set(phase_restrictions.get("excluded_movement_types", []))
        if trace.injury_state_used is not None:
            for pain_type in trace.injury_state_used.pain_on:
                excluded_mvt_types.add(pain_type)

    removed_exercises_list = [
        {"name": ex.name, "id": ex.id, "reason": reason}
        for ex, reason in trace.removed
    ]

    decision_steps = build_decision_trace(
        prompt=input.prompt,
        member_id=input.member_id,
        injury_joint=injury_joint_slug,
        injured_node_ids=injured_node_ids_set,
        excluded_movement_types=excluded_mvt_types,
        available_equipment=available_equipment,
        dislikes=dislikes,
        safe_count=len(trace.safe),
        removed_count=len(trace.removed),
        removed_exercises=removed_exercises_list,
        variant_ids=["primary"],
        timings={
            "movement_type_exclusion": filter_ms,
            "llm_structuring": llm_ms,
        },
    )

    # ------------------------------------------------------------------
    # 6. Build PROV-O provenance documents (Phase 12)
    # ------------------------------------------------------------------
    ended_at = datetime.now(tz=timezone.utc)
    prov_documents: dict[str, Any] = {}

    try:
        from app.generator.provenance import build_provenance, prov_document_to_dict

        for variant in variants:
            constraints = {
                "prompt": input.prompt,
                "member_id": input.member_id,
                "time_window_minutes": input.time_window_minutes,
                "equipment_available": sorted(available_equipment),
                "variant_id": variant.variant_id,
            }
            prov_doc = build_provenance(
                plan=variant.plan,
                trace=trace,
                constraints=constraints,
                timing=(started_at, ended_at),
                variant_id=variant.variant_id,
                injury_joint=injury_joint_slug,
            )
            prov_documents[variant.variant_id] = prov_document_to_dict(prov_doc)
    except Exception:
        # PROV-O is enrichment — never let it fail the generation pipeline
        prov_documents = {}

    return GeneratorOutput(
        variants=variants,
        trace=trace,
        selected_variant_id=None,
        decision_trace=decision_steps,
        prov_documents=prov_documents if prov_documents else None,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_safe_preview(member: MemberContext, kg: MovementKG) -> tuple[int, int, float]:
    """
    Run ONLY the deterministic safety filter for a quick streaming preview.

    Returns (safe_count, removed_count, filter_ms). Read-only and cheap — mirrors
    the filter stage of generate_workout() so the coach sees the safe/filtered
    counts within ~1s, before the LLM call. Does not affect generate_workout().
    """
    available_equipment: set[str] = set(member.equipment_available)
    dislikes: set[str] = set(member.preferences.dislikes)
    candidates = kg.all_exercises()

    injury: Injury | None = None
    if member.injuries:
        from app.api.routes.injury import _load_injury, _promote_injury

        first_raw = member.injuries[0]
        try:
            injury = _load_injury(member.profile.id, first_raw.id)
        except Exception:
            try:
                injury = _promote_injury(first_raw, member.profile.id)
            except Exception:
                injury = None

    t0 = time.perf_counter()
    if injury is not None:
        trace = conditional_safety_filter(
            candidates=candidates,
            injury=injury,
            available_equipment=available_equipment,
            excluded_ids=set(),
            dislikes=dislikes,
            kg=kg,
        )
        safe_n, removed_n = len(trace.safe), len(trace.removed)
    else:
        from app.graph.safety_filter import safety_filter

        base = safety_filter(
            candidates=candidates,
            injured_joints=[],
            available_equipment=available_equipment,
            excluded_ids=set(),
            dislikes=dislikes,
            kg=kg,
        )
        safe_n, removed_n = len(base.safe), len(base.removed)
    return safe_n, removed_n, (time.perf_counter() - t0) * 1000.0


async def generate_workout_stream(
    input: GeneratorInput,
    kg: MovementKG,
    member: MemberContext,
    llm: BaseChatModel,
) -> AsyncIterator[dict | GeneratorOutput]:
    """
    Streaming variant of generate_workout.

    Yields progress status dicts for perceived speed, then the authoritative
    GeneratorOutput as the final item:
      {"stage": "resolve"}
      {"stage": "safety", "safe_count": N, "removed_count": M, "filter_ms": X}
      {"stage": "structuring"}
      <GeneratorOutput>          # final

    The deterministic stages complete in ~1s so the coach sees the safety result
    immediately; the plan arrives when the single LLM call finishes. The final
    result comes from the unchanged generate_workout(), so behavior is identical.
    """
    yield {"stage": "resolve", "prompt": input.prompt}

    try:
        loop = asyncio.get_event_loop()
        safe_n, removed_n, filter_ms = await loop.run_in_executor(
            None, lambda: _compute_safe_preview(member, kg)
        )
        yield {
            "stage": "safety",
            "safe_count": safe_n,
            "removed_count": removed_n,
            "filter_ms": round(filter_ms, 1),
        }
    except Exception:
        yield {"stage": "safety"}

    # Engine-aware status: hybrid assembles deterministically then narrates;
    # the llm engine structures the whole plan.
    yield {"stage": "structuring", "engine": input.engine}

    output = await generate_workout(input=input, kg=kg, member=member, llm=llm)
    yield output


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
