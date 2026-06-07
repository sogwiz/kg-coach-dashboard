"""
In-memory plan store — Phase 6 (multi-member, 3 variants).

Persists the most recently generated GeneratorOutput per member so the
Copilot (Phase 7) can retrieve the current workout and answer questions
about it ("what stimulus does this target?", "why were these exercises
chosen?", "compare the strength vs conditioning variant").

Pattern mirrors the Phase 5 check-in store in app/api/routes/injury.py:
a module-level dict keyed by member_id, process-lifetime lifetime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.generator.pipeline import GeneratorOutput

# ---------------------------------------------------------------------------
# In-memory store (process lifetime)
# ---------------------------------------------------------------------------

# member_id -> most recently generated GeneratorOutput (3 variants + shared trace)
_plan_store: dict[str, "GeneratorOutput"] = {}


def set_current_plan(member_id: str, output: "GeneratorOutput") -> None:
    """
    Persist the most recently generated plan (all 3 variants) for a member.

    Overwrites any previous plan for the same member_id.
    The output must contain exactly 3 variants (strength, conditioning, mobility).
    """
    _plan_store[member_id] = output


def get_current_plan(member_id: str) -> "GeneratorOutput | None":
    """
    Retrieve the most recently generated plan for a member.

    Returns None if no plan has been generated yet for this member.
    """
    return _plan_store.get(member_id)


def select_variant(member_id: str, variant_id: str) -> "GeneratorOutput | None":
    """
    Record the coach's variant selection for a member.

    Mutates the stored GeneratorOutput in-place to set selected_variant_id,
    then returns the updated output.

    Parameters
    ----------
    member_id:
        The member whose plan is being updated.
    variant_id:
        The variant the coach selected: "strength", "conditioning", or "mobility".

    Returns
    -------
    The updated GeneratorOutput with selected_variant_id set, or None if no
    plan has been generated for this member yet.
    """
    output = _plan_store.get(member_id)
    if output is None:
        return None

    # Validate that the variant_id exists in the stored output
    known_ids = {v.variant_id for v in output.variants}
    if variant_id not in known_ids:
        return None

    output.selected_variant_id = variant_id
    return output


def clear_store() -> None:
    """
    Clear all stored plans.

    Useful for test isolation — call at the start or teardown of tests
    that exercise the store.
    """
    _plan_store.clear()
