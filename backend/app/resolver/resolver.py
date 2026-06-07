"""
3-Pass Concept Resolver
=======================

Resolves a free-text term to an ontology Concept via three sequential passes:

  Pass 1 — Exact
      Normalise to lowercase + strip whitespace; look up directly in the label
      index (pref_label + alt_labels).  Confidence = 1.0.

  Pass 2 — Fuzzy
      rapidfuzz.fuzz.ratio at threshold 90.  Strict character-level similarity
      so partial-containment matches (e.g. "bad lower back" ≈ "lower back")
      do NOT leak through — those are better handled by the embedding pass.
      Confidence = score / 100.

  Pass 3 — Embedding
      Sentence-transformer cosine similarity (all-MiniLM-L6-v2).
      Thresholds:
        ≥ EMBEDDING_RESOLVED_THRESHOLD  → status "resolved"
        ≥ EMBEDDING_LOW_CONF_THRESHOLD  → status "low_confidence"
        < EMBEDDING_LOW_CONF_THRESHOLD  → status "no_match"

Typed degradation
-----------------
  Resolution.status is one of:
    "resolved"        — confident single match, safe to use programmatically
    "low_confidence"  — best guess available; caller should surface candidates
                        to a human or LLM for disambiguation
    "no_match"        — nothing found above any threshold

Usage
-----
    from app.resolver.resolver import resolve, Resolution
    from app.ontology.loader import load_concept_catalog
    from app.resolver.embeddings import precompute_embeddings

    catalog = load_concept_catalog()
    corpus, cids = precompute_embeddings(list(catalog.values()))

    res = resolve("posterior chain", catalog, corpus, cids)
    # Resolution(status='resolved', concept='hamstrings', confidence=1.0, pass_used='exact')
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from app.ontology.concepts import Concept
from app.resolver.embeddings import cosine_search, get_model
from app.resolver.fuzzy import fuzzy_match

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

FUZZY_THRESHOLD: float = 90.0
"""Minimum fuzz.ratio score [0, 100] for the fuzzy pass to accept a match."""

EMBEDDING_RESOLVED_THRESHOLD: float = 0.60
"""
Minimum cosine similarity for the embedding pass to emit status='resolved'.
Values in [0, 1].
"""

EMBEDDING_LOW_CONF_THRESHOLD: float = 0.40
"""
Minimum cosine similarity for the embedding pass to emit status='low_confidence'.
Below this → 'no_match'.
"""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class Resolution:
    """
    The outcome of a resolve() call.

    Attributes
    ----------
    status:
        "resolved"       — confident single match
        "low_confidence" — best guess; surface candidates for disambiguation
        "no_match"       — nothing above any threshold
    concept:
        The matched concept_id (catalog slug), or None if no_match.
    confidence:
        Normalised confidence in [0, 1]:
          - exact  pass → 1.0
          - fuzzy  pass → fuzz.ratio / 100
          - embedding pass → cosine similarity
        None if no_match.
    pass_used:
        Which pass produced the result ("exact", "fuzzy", "embedding"), or
        None if no_match.
    candidates:
        For low_confidence results: a list of (concept_id, score) pairs
        sorted by descending score.  Empty for resolved / no_match.
    """

    status: Literal["resolved", "low_confidence", "no_match"]
    concept: str | None = None
    confidence: float | None = None
    pass_used: Literal["exact", "fuzzy", "embedding"] | None = None
    candidates: list[tuple[str, float]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Label index helpers
# ---------------------------------------------------------------------------


def _build_label_index(catalog: dict[str, Concept]) -> dict[str, str]:
    """
    Build a normalised-label → concept_id lookup covering pref_label and
    all alt_labels for every concept in the catalog.
    """
    index: dict[str, str] = {}
    for concept_id, concept in catalog.items():
        index[concept.pref_label.lower().strip()] = concept_id
        for alt in concept.alt_labels:
            index[alt.lower().strip()] = concept_id
    return index


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve(
    term: str,
    catalog: dict[str, Concept],
    corpus: np.ndarray,
    concept_ids: list[str],
) -> Resolution:
    """
    Resolve a free-text term to an ontology concept via 3 sequential passes.

    Parameters
    ----------
    term:
        The raw input string to resolve (e.g. "posterior chain", "bad lower back").
    catalog:
        The concept catalog, keyed by concept_id.
    corpus:
        Pre-computed embedding matrix from precompute_embeddings().
        Shape (N, D), L2-normalised rows.
    concept_ids:
        Parallel list of concept_ids for each row in corpus.

    Returns
    -------
    Resolution with status, concept, confidence, pass_used, and candidates.
    """
    label_index = _build_label_index(catalog)

    # ------------------------------------------------------------------
    # Pass 1: Exact
    # ------------------------------------------------------------------
    norm_term = term.lower().strip()
    if norm_term in label_index:
        return Resolution(
            status="resolved",
            concept=label_index[norm_term],
            confidence=1.0,
            pass_used="exact",
        )

    # ------------------------------------------------------------------
    # Pass 2: Fuzzy
    # ------------------------------------------------------------------
    fuzzy_result = fuzzy_match(term, label_index, threshold=FUZZY_THRESHOLD)
    if fuzzy_result is not None:
        concept_id, score = fuzzy_result
        return Resolution(
            status="resolved",
            concept=concept_id,
            confidence=score / 100.0,
            pass_used="fuzzy",
        )

    # ------------------------------------------------------------------
    # Pass 3: Embedding
    # ------------------------------------------------------------------
    if corpus.shape[0] == 0:
        return Resolution(status="no_match")

    model = get_model()
    query_embed: np.ndarray = model.encode(
        [term],
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )[0]

    hits = cosine_search(query_embed, corpus, threshold=EMBEDDING_LOW_CONF_THRESHOLD)

    if not hits:
        return Resolution(status="no_match")

    # Deduplicate: best score per concept_id
    best_per_concept: dict[str, float] = {}
    for idx, score in hits:
        cid = concept_ids[idx]
        if cid not in best_per_concept or score > best_per_concept[cid]:
            best_per_concept[cid] = score

    ranked = sorted(best_per_concept.items(), key=lambda x: x[1], reverse=True)
    top_concept, top_score = ranked[0]

    if top_score >= EMBEDDING_RESOLVED_THRESHOLD:
        return Resolution(
            status="resolved",
            concept=top_concept,
            confidence=float(top_score),
            pass_used="embedding",
        )
    else:
        # Low confidence — return candidates for disambiguation
        candidates = [(cid, score) for cid, score in ranked[:5]]
        return Resolution(
            status="low_confidence",
            concept=top_concept,
            confidence=float(top_score),
            pass_used="embedding",
            candidates=candidates,
        )
