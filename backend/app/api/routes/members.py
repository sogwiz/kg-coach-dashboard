"""
Members API routes — Phase 6 (multi-member foundation).

Endpoints:
  GET  /api/members                  — list all known members (for the UI switcher)
  GET  /api/members/{member_id}      — full context for a specific member
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.data.loader import list_members, load_member_context
from app.generator.workout_send_store import was_workout_sent_today
from app.models.member import MemberContext, MemberSummary

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=None)
async def get_members() -> list[dict]:
    """
    Return lightweight summaries for all known members.

    Used by the coach dashboard member-switcher UI to populate the member list.
    Includes workout_sent_today flag for each member.
    """
    summaries = list_members()
    result = []
    for m in summaries:
        d = m.model_dump()
        d["workout_sent_today"] = was_workout_sent_today(m.member_id)
        result.append(d)
    return result


@router.get("/{member_id}", response_model=MemberContext)
async def get_member(member_id: str) -> MemberContext:
    """
    Return the full context for a specific member.

    Raises 404 if the member_id is not found in any data file.
    """
    try:
        return load_member_context(member_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
