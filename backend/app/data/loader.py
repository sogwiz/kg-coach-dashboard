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
_MOVEMENTS_PATH = _DATA_DIR / "exercise_movements.json"
_MEMBER_PATH = _DATA_DIR / "member-context.json"


def load_exercises() -> list[Exercise]:
    """
    Load the exercise catalog from data/exercises.json and merge in
    movement-type annotations from data/exercise_movements.json.

    The joint_movements field is populated from the annotations file;
    exercises without an annotation entry get an empty dict (safe default).
    """
    raw = json.loads(_EXERCISES_PATH.read_text(encoding="utf-8"))

    # Load movement annotations if the file exists
    joint_movements_by_id: dict[str, dict] = {}
    if _MOVEMENTS_PATH.exists():
        movements_raw = json.loads(_MOVEMENTS_PATH.read_text(encoding="utf-8"))
        for ex_id, annotation in movements_raw.get("annotations", {}).items():
            joint_movements_by_id[ex_id] = annotation.get("joint_movements", {})

    exercises: list[Exercise] = []
    for item in raw:
        ex = Exercise.model_validate(item)
        if ex.id in joint_movements_by_id:
            ex = ex.model_copy(
                update={"joint_movements": joint_movements_by_id[ex.id]}
            )
        exercises.append(ex)

    return exercises


def load_member_context() -> MemberContext:
    """Load the synthetic member from data/member-context.json."""
    raw = json.loads(_MEMBER_PATH.read_text(encoding="utf-8"))
    # Strip the internal meta key before validating
    raw.pop("_note", None)
    return MemberContext.model_validate(raw)
