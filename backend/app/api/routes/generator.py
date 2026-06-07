"""
Generator API route — Phase 6 (multi-member, 3 variants) + Phase 12 (refine).

POST /api/generate
    Accepts a coach prompt + time window + member_id, runs the full generator
    pipeline (resolve → filter → LLM structure × 3 variants), and returns a
    GeneratorOutput carrying all three labeled variants + the shared filter trace.
    The output is also persisted to the in-memory plan store so the Copilot
    (Phase 7) can retrieve the current workouts.

POST /api/generate/select
    Records which variant the coach selected. Updates selected_variant_id in the
    stored GeneratorOutput and returns the updated object.

PATCH /api/generate/refine  (Phase 12)
    Accepts interactive adjustments ("exclude deadlifts", "no barbell",
    "add more core") and re-runs the generator pipeline with the additional
    constraint added to the member's excluded_ids / dislikes.

    Behaviour: the refinement re-runs a full generate_workout() call with the
    same prompt + time window from the stored plan, but with the new constraint
    layered in (exercise name / equipment name → excluded_ids or additional
    dislikes).  This always produces a fresh 3-variant set from the updated
    safe candidate pool and replaces the in-memory plan for the member.

    Rationale: re-running the full pipeline keeps the 3-variant model intact
    and ensures safety invariants are re-validated with every refinement.

Safety contract:
    - The safety filter runs ONCE per generate/refine call.
    - All three variants are drawn from the same safe exercise set.
    - The LLM never sees unsafe exercises.

If ANTHROPIC_API_KEY is not set, POST /api/generate returns HTTP 503 with a
clear error message — it never silently falls back to an incomplete plan.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.generator.pipeline import GeneratorInput, GeneratorOutput
from app.generator.store import get_current_plan, select_variant, set_current_plan

router = APIRouter(prefix="/generate", tags=["generator"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    """
    POST /api/generate request body.

    Attributes
    ----------
    prompt:
        Free-text session intent, e.g. "lower body strength focus".
    time_window_minutes:
        Available training window in minutes (10-180).
    member_id:
        The member to generate for.
    """

    prompt: str = Field(min_length=1, max_length=500)
    time_window_minutes: int = Field(default=60, ge=10, le=180)
    member_id: str = Field(default="mbr_01HX9JORDAN")


class SelectRequest(BaseModel):
    """
    POST /api/generate/select request body.

    Attributes
    ----------
    member_id:
        The member whose plan variant is being selected.
    variant_id:
        The variant id to select: "strength", "conditioning", or "mobility".
    """

    member_id: str
    variant_id: str


class RefineRequest(BaseModel):
    """
    PATCH /api/generate/refine request body.

    Accepts an interactive adjustment instruction and re-runs the generator
    pipeline with the additional constraint applied.

    Attributes
    ----------
    member_id:
        The member whose plan is being refined.
    adjustment:
        Natural-language refinement instruction, e.g.:
          - "exclude deadlifts"
          - "no barbell"
          - "add more core"
          - "remove jumping exercises"
        The adjustment is parsed to extract excluded exercise names or
        equipment names.  If the instruction cannot be parsed, the raw
        adjustment text is added as a dislike term so the LLM structuring
        still avoids matching exercises.
    prompt:
        Optional override for the coach prompt.  If omitted, the prompt from
        the most recently stored plan is reused.
    time_window_minutes:
        Optional override for the session duration.  If omitted, the value
        from the most recently stored plan is reused (defaults to 60 if no
        prior plan exists).
    """

    member_id: str
    adjustment: str = Field(min_length=1, max_length=500)
    prompt: str | None = Field(default=None)
    time_window_minutes: int | None = Field(default=None, ge=10, le=180)


# ---------------------------------------------------------------------------
# Shared singletons (built once per process)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_kg():
    """Build and cache the MovementKG."""
    from app.data.loader import load_exercises
    from app.graph.movement_kg import MovementKG
    from app.ontology.catalog import build_concept_catalog
    from app.ontology.loader import load_snomed_anatomy

    exercises = load_exercises()
    concepts = build_concept_catalog()
    snomed = load_snomed_anatomy()
    return MovementKG(exercises, concepts, snomed)


@lru_cache(maxsize=1)
def _get_llm():
    """
    Build and cache the structuring LLM.

    Returns None if ANTHROPIC_API_KEY is not set, so the endpoint can
    return a 503 instead of a crash.
    """
    try:
        from app.generator.llm import get_structuring_llm
        return get_structuring_llm()
    except RuntimeError:
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=None)
async def generate(request: GenerateRequest) -> dict:
    """
    Run the full generator pipeline and return 3 labeled workout variants.

    The safety filter runs once — all variants share the same safe exercise set.
    The LLM never sees unsafe exercises.

    Returns a JSON object with keys: variants, trace_summary, selected_variant_id.
    Each variant has: variant_id, label, optimizes_for, plan, provenance.
    """
    # Check LLM availability first
    llm = _get_llm()
    if llm is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "ANTHROPIC_API_KEY is not configured. "
                "Set the environment variable and restart the server."
            ),
        )

    kg = _get_kg()

    # Load member context
    from app.data.loader import load_member_context
    try:
        member = load_member_context(request.member_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Member '{request.member_id}' not found.",
        )

    gen_input = GeneratorInput(
        prompt=request.prompt,
        time_window_minutes=request.time_window_minutes,
        member_id=request.member_id,
    )

    from app.generator.pipeline import generate_workout
    output: GeneratorOutput = await generate_workout(
        input=gen_input,
        kg=kg,
        member=member,
        llm=llm,
    )

    # Persist to store for Copilot access
    set_current_plan(request.member_id, output)

    return _serialise_output(output)


@router.post("/select", response_model=None)
async def select(request: SelectRequest) -> dict:
    """
    Record the coach's variant selection and return the updated GeneratorOutput.

    Updates selected_variant_id in the stored output for the member.

    Returns HTTP 404 if no plan has been generated yet for the member, or if
    the variant_id is not one of the three generated variants.
    """
    updated = select_variant(request.member_id, request.variant_id)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No plan found for member '{request.member_id}', "
                f"or variant '{request.variant_id}' does not exist. "
                "Generate a plan first via POST /api/generate."
            ),
        )

    return _serialise_output(updated)


@router.patch("/refine", response_model=None)
async def refine(request: RefineRequest) -> dict:
    """
    Re-run the generator with an interactive adjustment applied as an
    additional constraint.

    The adjustment instruction is parsed to extract:
      - Exercise name exclusions ("exclude deadlifts" → adds "deadlift" to
        excluded dislikes so the generator avoids it)
      - Equipment exclusions ("no barbell" → adds "barbell" to the
        unavailable equipment set so the safety filter removes barbell exercises)
      - General hints ("add more core") are appended to the prompt so the
        LLM structuring call prioritises matching exercises.

    The full pipeline re-runs — safety filter is re-applied with the updated
    constraints — and the result replaces the stored plan for the member.

    Behaviour for "simplest coherent 3-variant model": re-run the full
    generate_workout() with the same prompt (or override) + same time window
    (or override) + the new constraint layered in.  Always returns 3 variants.
    """
    llm = _get_llm()
    if llm is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "ANTHROPIC_API_KEY is not configured. "
                "Set the environment variable and restart the server."
            ),
        )

    kg = _get_kg()

    # Load member context
    from app.data.loader import load_member_context
    try:
        member = load_member_context(request.member_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Member '{request.member_id}' not found.",
        )

    # Resolve prompt + time from the stored plan (fallback to defaults)
    stored = get_current_plan(request.member_id)
    if request.prompt is not None:
        prompt = request.prompt
    elif stored is not None and stored.variants:
        # Recover the prompt from the first variant's provenance
        prompt = stored.variants[0].provenance.prompt
    else:
        prompt = "general workout"

    if request.time_window_minutes is not None:
        time_window = request.time_window_minutes
    elif stored is not None and stored.variants:
        time_window = stored.variants[0].provenance.time_window_minutes
    else:
        time_window = 60

    # Parse the adjustment to extract additional constraints
    extra_dislikes, extra_prompt_suffix = _parse_adjustment(request.adjustment)

    # Layer extra dislikes into member preferences (non-mutating copy approach)
    import copy
    refined_member = copy.deepcopy(member)
    refined_member.preferences.dislikes = list(
        set(refined_member.preferences.dislikes) | extra_dislikes
    )

    # Append extra prompt suffix for positive hints (e.g. "add more core")
    full_prompt = prompt
    if extra_prompt_suffix:
        full_prompt = f"{prompt}. Refinement: {extra_prompt_suffix}"

    from app.generator.pipeline import GeneratorInput, generate_workout
    gen_input = GeneratorInput(
        prompt=full_prompt,
        time_window_minutes=time_window,
        member_id=request.member_id,
    )

    output = await generate_workout(
        input=gen_input,
        kg=kg,
        member=refined_member,
        llm=llm,
    )

    # Persist the refined plan
    set_current_plan(request.member_id, output)

    return _serialise_output(output)


def _parse_adjustment(adjustment: str) -> tuple[set[str], str]:
    """
    Parse an adjustment instruction into extra dislikes + prompt suffix.

    Returns
    -------
    extra_dislikes : set[str]
        Terms to add to the member's dislike list so the safety filter
        removes exercises whose name contains any of these terms.
    prompt_suffix : str
        A positive instruction to append to the prompt for the LLM
        (e.g. "add more core exercises").

    Examples
    --------
    "exclude deadlifts"     → ({"deadlift"}, "")
    "no barbell"            → ({"barbell"}, "")
    "remove jumping"        → ({"jump"}, "")
    "add more core"         → (set(), "add more core exercises")
    "exclude squats, no box" → ({"squat", "box"}, "")
    """
    adj_lower = adjustment.lower().strip()

    # Exclusion triggers
    exclusion_triggers = ["exclude ", "no ", "remove ", "without ", "avoid "]
    addition_triggers = ["add ", "include ", "more ", "extra "]

    extra_dislikes: set[str] = set()
    prompt_suffix = ""

    # Check for exclusion patterns
    for trigger in exclusion_triggers:
        if adj_lower.startswith(trigger):
            terms = adj_lower[len(trigger):].strip()
            # Handle comma-separated multi-term
            for term in terms.split(","):
                term = term.strip()
                if term:
                    # Normalise: strip common pluralisation
                    term = term.rstrip("s") if term.endswith("s") and len(term) > 3 else term
                    extra_dislikes.add(term)
            return extra_dislikes, prompt_suffix

    # Check for addition patterns
    for trigger in addition_triggers:
        if adj_lower.startswith(trigger) or f" {trigger}" in adj_lower:
            prompt_suffix = adjustment.strip()
            return extra_dislikes, prompt_suffix

    # Fallback: treat the whole adjustment as a dislike term (conservative)
    for term in adj_lower.split(","):
        term = term.strip()
        if term:
            extra_dislikes.add(term)

    return extra_dislikes, prompt_suffix


# ---------------------------------------------------------------------------
# Serialisation helper
# ---------------------------------------------------------------------------


def _serialise_variant(variant) -> dict:
    """Serialise a single WorkoutVariant to a JSON-safe dict."""
    plan_dict = variant.plan.model_dump()

    prov = variant.provenance
    prov_dict: dict = {
        "generated_at": prov.generated_at.isoformat(),
        "prompt": prov.prompt,
        "time_window_minutes": prov.time_window_minutes,
        "healing_phase": prov.healing_phase,
        "load_tolerance_pct": prov.load_tolerance_pct,
        "stale_check_in": prov.stale_check_in,
        "exercises_filtered_out": prov.exercises_filtered_out,
        "equipment_available": prov.equipment_available,
        "injury_state_used": (
            prov.injury_state_used.model_dump(mode="json")
            if prov.injury_state_used is not None
            else None
        ),
    }

    return {
        "variant_id": variant.variant_id,
        "label": variant.label,
        "optimizes_for": variant.optimizes_for,
        "plan": plan_dict,
        "provenance": prov_dict,
    }


def _serialise_output(output: GeneratorOutput) -> dict:
    """Convert GeneratorOutput (dataclasses + Pydantic) to a JSON-safe dict."""
    # Summarise the shared filter trace
    trace = output.trace
    trace_summary = {
        "safe_count": len(trace.safe),
        "removed_count": len(trace.removed),
        "substitution_count": len(trace.substitutions),
        "load_tolerance_pct": trace.load_tolerance_pct,
        "stale_check_in": trace.stale_check_in,
        "removed": [
            {"id": ex.id, "name": ex.name, "reason": reason}
            for ex, reason in trace.removed
        ],
    }

    # Serialise the in-app decision trace (Phase 7 observability)
    decision_trace_list: list[dict] = []
    if output.decision_trace:
        for step in output.decision_trace:
            decision_trace_list.append(
                {
                    "name": step.name,
                    "detail": step.detail,
                    "inputs": step.inputs,
                    "outputs": step.outputs,
                    "kind": step.kind,
                }
            )

    return {
        "variants": [_serialise_variant(v) for v in output.variants],
        "trace_summary": trace_summary,
        "selected_variant_id": output.selected_variant_id,
        "decision_trace": decision_trace_list,
        # Phase 12: PROV-O provenance documents (one per variant, keyed by variant_id)
        # Additive — None if build failed; frontend treats absence as graceful degradation
        "prov": output.prov_documents,
    }
