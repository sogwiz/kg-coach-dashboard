"""
Data loader — reads seed JSON files into Pydantic models.

Paths are resolved relative to this file so the loader works regardless of
the current working directory.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models.exercise import Exercise
from app.models.member import MemberContext

# Root of the repo (two levels up from this file: app/data/loader.py → app → backend → repo)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_DIR = _REPO_ROOT / "data"

_EXERCISES_PATH = _DATA_DIR / "exercises.json"
_MEMBER_PATH = _DATA_DIR / "member-context.json"


def load_exercises() -> list[Exercise]:
    """Load the exercise catalog from data/exercises.json."""
    raw = json.loads(_EXERCISES_PATH.read_text(encoding="utf-8"))
    return [Exercise.model_validate(item) for item in raw]


def load_member_context() -> MemberContext:
    """Load the synthetic member from data/member-context.json."""
    raw = json.loads(_MEMBER_PATH.read_text(encoding="utf-8"))
    # Strip the internal meta key before validating
    raw.pop("_note", None)
    return MemberContext.model_validate(raw)
