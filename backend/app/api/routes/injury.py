"""
Injury check-in API routes — Phase 5.

Endpoints:
  POST   /members/{member_id}/injuries/{injury_id}/check-in
  GET    /members/{member_id}/injuries/{injury_id}/history
  PATCH  /members/{member_id}/injuries/{injury_id}/phase

The in-memory store is intentionally simple for Phase 5 — the member context
is loaded once at startup and mutations are stored in process memory.  A real
implementation would persist to a database.

State is keyed by (member_id, injury_id) → list[InjuryState].
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException

from app.models.injury import (
    HealingPhase,
    Injury,
    InjuryState,
    InjuryStateCreate,
)

router = APIRouter(prefix="/members", tags=["injury"])

# ---------------------------------------------------------------------------
# In-memory state store (process lifetime)
# ---------------------------------------------------------------------------

# (member_id, injury_id) -> list[InjuryState]
_state_store: dict[tuple[str, str], list[InjuryState]] = defaultdict(list)

# (member_id, injury_id) -> phase_override | None
_phase_override_store: dict[tuple[str, str], HealingPhase | None] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_injury(member_id: str, injury_id: str) -> Injury:
    """
    Load the Injury record from the member context, merging in any in-memory
    state mutations (check-ins and phase overrides).

    Raises HTTPException 404 if the member or injury is not found.
    """
    from app.data.loader import load_member_context

    try:
        member = load_member_context(member_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Member '{member_id}' not found")

    # Find the injury in the member context
    # The injury model in member.py is the thin stub; we need to promote it
    # to the full Injury model here.
    raw_injury = next(
        (inj for inj in member.injuries if inj.id == injury_id),
        None,
    )
    if raw_injury is None:
        raise HTTPException(
            status_code=404,
            detail=f"Injury '{injury_id}' not found for member '{member_id}'",
        )

    # Promote thin Injury stub to full Injury model
    injury = _promote_injury(raw_injury, member_id)

    # Merge in-memory states
    persisted_states = _state_store.get((member_id, injury_id), [])
    all_states = list(injury.states) + persisted_states

    # Apply phase override
    phase_override = _phase_override_store.get((member_id, injury_id))
    active_phase = phase_override or injury.computed_phase()

    return injury.model_copy(
        update={
            "states": all_states,
            "current_phase": active_phase,
            "phase_override": phase_override,
        }
    )


def _promote_injury(raw_injury, member_id: str) -> Injury:
    """
    Convert a thin member.Injury (the stub from Phase 1) to the full
    models.injury.Injury with default values where fields are missing.
    """
    # Handle both the old stub (member.Injury) and new full Injury
    if isinstance(raw_injury, Injury):
        return raw_injury

    # The stub has: id, region, joint, status, severity, since, notes, snomedct_hint
    # The full model needs: onset_date, diagnosis, snomed_code, current_phase
    from app.models.healing import compute_phase
    from datetime import date as date_cls

    onset_raw = getattr(raw_injury, "since", None) or getattr(raw_injury, "onset_date", None)
    if onset_raw is None:
        onset_date = date_cls.today()
    elif isinstance(onset_raw, str):
        onset_date = date_cls.fromisoformat(onset_raw)
    else:
        onset_date = onset_raw

    days = (date_cls.today() - onset_date).days
    phase = compute_phase(days)

    # Pull state history from the stub if it exists (new format)
    states: list[InjuryState] = []
    raw_states = getattr(raw_injury, "states", [])
    for s in raw_states:
        if isinstance(s, InjuryState):
            states.append(s)
        elif isinstance(s, dict):
            states.append(InjuryState.model_validate({**s, "injury_id": raw_injury.id}))

    return Injury(
        id=raw_injury.id,
        region=raw_injury.region,
        joint=raw_injury.joint,
        diagnosis=getattr(raw_injury, "diagnosis", None)
            or getattr(raw_injury, "notes", None)
            or raw_injury.joint,
        snomed_code=getattr(raw_injury, "snomedct_hint", None)
            or getattr(raw_injury, "snomed_code", None),
        onset_date=onset_date,
        current_phase=phase,
        phase_override=getattr(raw_injury, "phase_override", None),
        states=states,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/{member_id}/injuries/{injury_id}/check-in", response_model=InjuryState)
async def record_check_in(
    member_id: str,
    injury_id: str,
    body: InjuryStateCreate,
) -> InjuryState:
    """
    Record today's injury state for the given member and injury.

    The state is appended to the in-memory store.  Multiple check-ins per day
    are allowed; the most recent is used by the conditional filter.
    """
    _load_injury(member_id, injury_id)  # validates member + injury exist

    state = InjuryState(
        injury_id=injury_id,
        recorded_at=datetime.now(tz=timezone.utc),
        inflammation=body.inflammation,
        pain_on=body.pain_on,
        subjective_pain=body.subjective_pain,
        load_tolerance_pct=body.load_tolerance_pct,
        notes=body.notes,
    )
    _state_store[(member_id, injury_id)].append(state)
    return state


@router.get(
    "/{member_id}/injuries/{injury_id}/history",
    response_model=list[InjuryState],
)
async def get_injury_history(
    member_id: str,
    injury_id: str,
    days: int = 14,
) -> list[InjuryState]:
    """
    Return check-in history for the past N days (default 14).

    Results are sorted newest-first.
    """
    injury = _load_injury(member_id, injury_id)

    cutoff = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    cutoff = cutoff - timedelta(days=days)

    recent = [
        s for s in injury.states
        if s.recorded_at >= cutoff
    ]
    return sorted(recent, key=lambda s: s.recorded_at, reverse=True)


@router.patch("/{member_id}/injuries/{injury_id}/phase", response_model=Injury)
async def override_phase(
    member_id: str,
    injury_id: str,
    phase: HealingPhase,
) -> Injury:
    """
    Coach / PT override for healing phase.

    Sets an explicit phase that takes precedence over the computed phase.
    Pass the body as a JSON string, e.g. `"remodeling"`.
    """
    injury = _load_injury(member_id, injury_id)

    _phase_override_store[(member_id, injury_id)] = phase

    return injury.model_copy(
        update={
            "current_phase": phase,
            "phase_override": phase,
        }
    )
