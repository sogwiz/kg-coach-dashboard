"""
In-memory store for tracking sent workouts — Feature 1.

Tracks which members have received a workout today and stores the message
sent with it. Process-lifetime storage (same pattern as plan store).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import NamedTuple


class SentWorkoutRecord(NamedTuple):
    """Record of a workout sent to a member."""
    member_id: str
    variant_id: str
    sent_at: datetime
    message: str


# member_id -> SentWorkoutRecord (most recent send)
_sent_store: dict[str, SentWorkoutRecord] = {}


def mark_workout_sent(
    member_id: str,
    variant_id: str,
    message: str,
) -> SentWorkoutRecord:
    """Record that a workout was sent to a member."""
    record = SentWorkoutRecord(
        member_id=member_id,
        variant_id=variant_id,
        sent_at=datetime.now(),
        message=message,
    )
    _sent_store[member_id] = record
    return record


def get_sent_workout(member_id: str) -> SentWorkoutRecord | None:
    """Get the most recent sent workout for a member."""
    return _sent_store.get(member_id)


def was_workout_sent_today(member_id: str) -> bool:
    """Check if a workout was sent to this member today."""
    record = _sent_store.get(member_id)
    if record is None:
        return False
    return record.sent_at.date() == date.today()


def get_today_sent_members() -> set[str]:
    """Get all member IDs who received a workout today."""
    today = date.today()
    return {
        member_id
        for member_id, record in _sent_store.items()
        if record.sent_at.date() == today
    }


def clear_store() -> None:
    """Clear all sent records (for tests)."""
    _sent_store.clear()
