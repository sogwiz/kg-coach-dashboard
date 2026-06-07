"""
Ontology loader — boots the concept catalog and SNOMED anatomy graph at startup.

Provides:
  load_concept_catalog() -> dict[str, Concept]
  load_snomed_anatomy()  -> dict[str, SnomedConcept]

Both loaders are idempotent and cache their result after the first call.
The SNOMED snapshot is read from the baked JSON file committed to the repo,
so no network access is required at runtime.

Phase 6 (multi-member): the anatomy snapshot was extended from snomed_knee.json
to snomed_anatomy.json, adding the lumbar spine subtree for Mico's injury.
The loader transparently falls back to snomed_knee.json for backward
compatibility if snomed_anatomy.json is not present.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from app.ontology.catalog import build_concept_catalog
from app.ontology.concepts import Concept

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ONTOLOGY_DIR = Path(__file__).resolve().parent
_SNOMED_ANATOMY_PATH = _ONTOLOGY_DIR / "snomed_anatomy.json"
_SNOMED_KNEE_PATH = _ONTOLOGY_DIR / "snomed_knee.json"   # legacy name (fallback)


def _snomed_path() -> Path:
    """Return the SNOMED snapshot path, preferring the extended anatomy file."""
    if _SNOMED_ANATOMY_PATH.exists():
        return _SNOMED_ANATOMY_PATH
    if _SNOMED_KNEE_PATH.exists():
        return _SNOMED_KNEE_PATH
    raise FileNotFoundError(
        f"SNOMED snapshot not found at {_SNOMED_ANATOMY_PATH} or {_SNOMED_KNEE_PATH}. "
        "Run `uv run python scripts/fetch_snomed.py` from the repo root."
    )


# ---------------------------------------------------------------------------
# SNOMED models
# ---------------------------------------------------------------------------


class SnomedEdge(BaseModel):
    """A directed edge in the SNOMED anatomy graph."""

    from_code: str
    to_code: str
    relation: str  # "part-of" | "involves"


class SnomedConcept(BaseModel):
    """A single SNOMED CT concept node with its edge set."""

    code: str
    name: str
    pref_label: str
    type: str  # "joint" | "bone" | "muscle" | "ligament" | "cartilage" | "tendon" | "body_region" | "injury"
    # Codes of concepts this concept is part of (i.e. this --part-of--> parent)
    part_of: list[str] = []


class SnomedSnapshot(BaseModel):
    """
    The full baked SNOMED anatomy snapshot.

    Supports both the original knee-only format (snomed_knee.json) and the
    extended multi-region format (snomed_anatomy.json) that adds lumbar_concepts,
    lumbar_injury_concepts, and lumbar_edges.
    """

    terminology: str
    version: str
    source: str
    concepts: list[dict]
    injury_concepts: list[dict]
    edges: list[dict]
    # Phase 6 extensions (optional — absent in legacy snomed_knee.json)
    lumbar_concepts: list[dict] = []
    lumbar_injury_concepts: list[dict] = []
    lumbar_edges: list[dict] = []
    api_validated: bool = False
    api_concept_name: str | None = None


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_concept_catalog() -> dict[str, Concept]:
    """
    Load the canonical concept catalog.

    Returns a dict keyed by concept id (slug).
    Results are cached after the first call.
    """
    return build_concept_catalog()


@lru_cache(maxsize=1)
def load_snomed_anatomy() -> dict[str, SnomedConcept]:
    """
    Load the baked SNOMED anatomy snapshot (knee + lumbar spine).

    Returns a dict keyed by SNOMED concept code (string).
    Results are cached after the first call.

    Reads snomed_anatomy.json if present, falling back to snomed_knee.json.
    """
    path = _snomed_path()
    raw = json.loads(path.read_text(encoding="utf-8"))
    snapshot = SnomedSnapshot.model_validate(raw)

    # Build part-of lookup: code -> list of parent codes
    # Merge edges from both the core edge list and lumbar_edges
    all_edges = snapshot.edges + snapshot.lumbar_edges
    part_of_map: dict[str, list[str]] = {}
    for edge in all_edges:
        if edge["relation"] == "part-of":
            child = edge["from"]
            parent = edge["to"]
            part_of_map.setdefault(child, []).append(parent)

    # Index all concepts (anatomy + injury + lumbar extensions)
    all_concepts: dict[str, SnomedConcept] = {}

    def _add_concept(raw_concept: dict, concept_type_default: str = "body_region") -> None:
        code = raw_concept["code"]
        # Use declared type if present, else default
        ctype = raw_concept.get("type", concept_type_default)
        concept = SnomedConcept(
            code=code,
            name=raw_concept["name"],
            pref_label=raw_concept["pref_label"],
            type=ctype,
            part_of=part_of_map.get(code, []),
        )
        all_concepts[code] = concept

    def _add_injury_concept(raw_concept: dict) -> None:
        code = raw_concept["code"]
        if code not in all_concepts:
            concept = SnomedConcept(
                code=code,
                name=raw_concept["name"],
                pref_label=raw_concept["pref_label"],
                type="injury",
                part_of=[],
            )
            all_concepts[code] = concept

    # Core knee concepts
    for raw_concept in snapshot.concepts:
        _add_concept(raw_concept)

    # Core injury concepts (knee)
    for raw_injury in snapshot.injury_concepts:
        _add_injury_concept(raw_injury)

    # Lumbar anatomy concepts (Phase 6)
    for raw_concept in snapshot.lumbar_concepts:
        _add_concept(raw_concept)

    # Lumbar injury concepts (Phase 6)
    for raw_injury in snapshot.lumbar_injury_concepts:
        _add_injury_concept(raw_injury)

    return all_concepts


def get_descendants_by_part_of(
    snomed: dict[str, SnomedConcept], region_code: str
) -> set[str]:
    """
    Return all concept codes that are (transitively) part-of the given region.

    For example, get_descendants_by_part_of(snomed, "72696002") returns
    all concepts that are part of the knee region, including the knee joint,
    patellofemoral joint, menisci, ACL, etc.

    Likewise, get_descendants_by_part_of(snomed, "122496007") returns all
    concepts part of the lumbar spine region.
    """
    descendants: set[str] = set()
    queue = [region_code]
    visited: set[str] = set()

    while queue:
        current = queue.pop()
        if current in visited:
            continue
        visited.add(current)

        for code, concept in snomed.items():
            if current in concept.part_of and code not in visited:
                descendants.add(code)
                queue.append(code)

    return descendants
