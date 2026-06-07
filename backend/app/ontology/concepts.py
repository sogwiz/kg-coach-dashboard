"""
Concept model — a single ontology node with SKOS-style labels.

Follows SKOS (Simple Knowledge Organization System):
  - pref_label  ≡ skos:prefLabel  (canonical display form)
  - alt_labels  ≡ skos:altLabel   (synonyms / common names used for matching)
  - snomed_code ≡ a SNOMED CT concept identifier where one exists

The `type` discriminator maps to the six node families used across the
Movement KG and safety filter:

  joint        — anatomical joint (e.g. knee, shoulder)
  muscle       — muscle / muscle group (e.g. quadriceps, hamstrings)
  pattern      — movement pattern label (e.g. "lower push - squat")
  equipment    — physical equipment item (e.g. barbell, resistance band)
  injury       — clinical injury concept (e.g. PFPS, ACL tear)
  body_region  — broader anatomical region that subsumes joints (e.g. knee region)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Concept(BaseModel):
    """A canonical concept node in the movement / anatomy ontology."""

    id: str
    """Stable slug, e.g. 'knee', 'quadriceps', 'lower_push_squat'."""

    type: Literal["joint", "muscle", "pattern", "equipment", "injury", "body_region"]
    """Node family."""

    pref_label: str
    """SKOS prefLabel — the canonical human-readable name."""

    alt_labels: list[str] = []
    """SKOS altLabels — synonyms / alternate spellings used for fuzzy matching."""

    snomed_code: str | None = None
    """SNOMED CT concept code, if applicable."""
