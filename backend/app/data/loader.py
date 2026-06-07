"""
Data loader — reads seed JSON files into Pydantic models.

Paths are resolved relative to this file so the loader works regardless of
the current working directory.

Phase 6 (multi-member): adds list_members() and load_member_context(member_id).
The legacy no-argument load_member_context() signature is preserved for
backward compatibility — it returns Jordan's context when called without args.

Member data layout:
  data/members/<slug>.json   (new per-member files: jordan.json, mico.json, …)
  data/member-context.json   (legacy file; still valid; used as fallback)
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models.exercise import Exercise
from app.models.member import MemberContext, MemberSummary

# Root of the repo (two levels up from this file: app/data/loader.py → app → backend → repo)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_DIR = _REPO_ROOT / "data"

_EXERCISES_PATH = _DATA_DIR / "exercises.json"
_HYBRID_EXERCISES_PATH = _DATA_DIR / "exercises.hybrid.json"  # Phase 11 hybrid catalog
_MOVEMENTS_PATH = _DATA_DIR / "exercise_movements.json"
_MEMBER_PATH = _DATA_DIR / "member-context.json"      # legacy single-member file
_MEMBERS_DIR = _DATA_DIR / "members"                  # Phase 6 per-member directory

# Stable member_id for Jordan (sourced from the data)
_JORDAN_ID = "mbr_01HX9JORDAN"


# ---------------------------------------------------------------------------
# Exercise loading
# ---------------------------------------------------------------------------


def load_exercises() -> list[Exercise]:
    """
    Load the exercise catalog from data/exercises.json and merge in
    movement-type annotations from data/exercise_movements.json.

    Also merges exercises.hybrid.json (Phase 11: HYROX/tactical movements)
    when that file exists — hybrid exercises are appended to the base catalog.

    The joint_movements field is populated from the annotations file;
    exercises without an annotation entry get an empty dict (safe default).
    """
    raw = json.loads(_EXERCISES_PATH.read_text(encoding="utf-8"))

    # Merge hybrid exercises if the file exists (Phase 11)
    if _HYBRID_EXERCISES_PATH.exists():
        hybrid_raw = json.loads(_HYBRID_EXERCISES_PATH.read_text(encoding="utf-8"))
        raw = raw + hybrid_raw

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


# ---------------------------------------------------------------------------
# Member loading
# ---------------------------------------------------------------------------


def _load_member_from_path(path: Path) -> MemberContext:
    """Parse a member JSON file into a MemberContext, stripping internal meta keys."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("_note", None)
    raw.pop("member_id", None)   # top-level shortcut field; not part of MemberContext schema
    return MemberContext.model_validate(raw)


def _find_member_path(member_id: str) -> Path | None:
    """
    Locate the JSON file for the given member_id.

    Search order:
      1. data/members/<slug>.json files (any file whose top-level member_id matches)
      2. data/member-context.json (legacy file — Jordan only)

    Returns None if not found.
    """
    # Search per-member files
    if _MEMBERS_DIR.exists():
        for path in _MEMBERS_DIR.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if raw.get("member_id") == member_id or raw.get("profile", {}).get("id") == member_id:
                    return path
            except Exception:
                continue

    # Fall back to legacy single-member file for Jordan
    if _MEMBER_PATH.exists():
        try:
            raw = json.loads(_MEMBER_PATH.read_text(encoding="utf-8"))
            profile_id = raw.get("profile", {}).get("id", "")
            if profile_id == member_id:
                return _MEMBER_PATH
        except Exception:
            pass

    return None


def load_member_context(member_id: str | None = None) -> MemberContext:
    """
    Load a member's full context from disk.

    Parameters
    ----------
    member_id:
        The stable member id (e.g. "mbr_01HX9JORDAN", "mbr_MICO").
        When omitted, returns Jordan's context for backward compatibility.

    Raises
    ------
    ValueError
        If the member_id is not found in any known data file.
    """
    # Backward compatibility: no-arg call returns Jordan
    if member_id is None:
        member_id = _JORDAN_ID

    path = _find_member_path(member_id)
    if path is None:
        raise ValueError(
            f"Member '{member_id}' not found. "
            f"Check data/members/ or data/member-context.json."
        )
    return _load_member_from_path(path)


def list_members() -> list[MemberSummary]:
    """
    Return a lightweight summary for every known member.

    Used by GET /api/members to populate the UI member switcher.
    """
    summaries: list[MemberSummary] = []
    seen_ids: set[str] = set()

    # Collect from per-member directory
    if _MEMBERS_DIR.exists():
        for path in sorted(_MEMBERS_DIR.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                profile = raw.get("profile", {})
                mid = profile.get("id") or raw.get("member_id", "")
                if not mid or mid in seen_ids:
                    continue
                seen_ids.add(mid)

                injuries = raw.get("injuries", [])
                active_injury = injuries[0].get("region") if injuries else None

                adherence = raw.get("adherence", {})
                churn = raw.get("coach_brief", {}).get("churn_risk", {})

                summaries.append(
                    MemberSummary(
                        member_id=mid,
                        name=profile.get("name", mid),
                        age=profile.get("age", 0),
                        sex=profile.get("sex", ""),
                        churn_risk_level=churn.get("level", "unknown"),
                        adherence_trend=adherence.get("trend", "unknown"),
                        active_injury=active_injury,
                    )
                )
            except Exception:
                continue

    # Include legacy member-context.json if not already captured
    if _MEMBER_PATH.exists():
        try:
            raw = json.loads(_MEMBER_PATH.read_text(encoding="utf-8"))
            profile = raw.get("profile", {})
            mid = profile.get("id", "")
            if mid and mid not in seen_ids:
                seen_ids.add(mid)
                injuries = raw.get("injuries", [])
                active_injury = injuries[0].get("region") if injuries else None
                adherence = raw.get("adherence", {})
                churn = raw.get("coach_brief", {}).get("churn_risk", {})
                summaries.append(
                    MemberSummary(
                        member_id=mid,
                        name=profile.get("name", mid),
                        age=profile.get("age", 0),
                        sex=profile.get("sex", ""),
                        churn_risk_level=churn.get("level", "unknown"),
                        adherence_trend=adherence.get("trend", "unknown"),
                        active_injury=active_injury,
                    )
                )
        except Exception:
            pass

    return summaries
