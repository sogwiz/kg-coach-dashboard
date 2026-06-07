"""
Ontology loader — boots the concept catalog and SNOMED anatomy graph at startup.

Provides:
  load_concept_catalog() -> dict[str, Concept]
  load_snomed_anatomy()  -> dict[str, SnomedConcept]

Both loaders are idempotent and cache their result after the first call.
The SNOMED snapshot is read from the baked JSON file committed to the repo,
so no network access is required at runtime.
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
_SNOMED_PATH = _ONTOLOGY_DIR / "snomed_knee.json"


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
    """The full baked SNOMED knee snapshot."""

    terminology: str
    version: str
    source: str
    concepts: list[dict]
    injury_concepts: list[dict]
    edges: list[dict]
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
    Load the baked SNOMED knee subtree from snomed_knee.json.

    Returns a dict keyed by SNOMED concept code (string).
    Results are cached after the first call.

    Raises FileNotFoundError if snomed_knee.json has not been generated yet.
    Run `python scripts/fetch_snomed.py` from the repo root to generate it.
    """
    if not _SNOMED_PATH.exists():
        raise FileNotFoundError(
            f"SNOMED snapshot not found at {_SNOMED_PATH}. "
            "Run `uv run python scripts/fetch_snomed.py` from the repo root."
        )

    raw = json.loads(_SNOMED_PATH.read_text(encoding="utf-8"))
    snapshot = SnomedSnapshot.model_validate(raw)

    # Build part-of lookup: code -> list of parent codes
    part_of_map: dict[str, list[str]] = {}
    for edge in snapshot.edges:
        if edge["relation"] == "part-of":
            child = edge["from"]
            parent = edge["to"]
            part_of_map.setdefault(child, []).append(parent)

    # Index all concepts (anatomy + injury)
    all_concepts: dict[str, SnomedConcept] = {}

    for raw_concept in snapshot.concepts:
        code = raw_concept["code"]
        concept = SnomedConcept(
            code=code,
            name=raw_concept["name"],
            pref_label=raw_concept["pref_label"],
            type=raw_concept["type"],
            part_of=part_of_map.get(code, []),
        )
        all_concepts[code] = concept

    for raw_injury in snapshot.injury_concepts:
        code = raw_injury["code"]
        if code not in all_concepts:
            concept = SnomedConcept(
                code=code,
                name=raw_injury["name"],
                pref_label=raw_injury["pref_label"],
                type="injury",
                part_of=[],
            )
            all_concepts[code] = concept

    return all_concepts


def get_descendants_by_part_of(
    snomed: dict[str, SnomedConcept], region_code: str
) -> set[str]:
    """
    Return all concept codes that are (transitively) part-of the given region.

    For example, get_descendants_by_part_of(snomed, "72696002") returns
    all concepts that are part of the knee region, including the knee joint,
    patellofemoral joint, menisci, ACL, etc.
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
