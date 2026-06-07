"""
Fuzzy-match pass — thin wrapper around rapidfuzz.

Uses ``fuzz.ratio`` (strict character-level Levenshtein similarity) rather
than ``fuzz.WRatio`` so that partial containment matches (e.g. "bad lower back"
containing "lower back") do NOT trigger a false positive at threshold 90.
WRatio / partial_ratio would score those at 95+ which bypasses the embedding
pass we want to exercise for semantically-related but lexically-different terms.

API
---
fuzzy_match(term, labels, threshold=90) -> tuple[str, float] | None

    term     : the raw input string
    labels   : dict mapping normalised_label -> concept_id
    threshold: minimum fuzz.ratio score [0, 100] to consider a match

Returns (concept_id, score) or None if no label scores above threshold.
"""

from __future__ import annotations

from rapidfuzz import fuzz, process


def fuzzy_match(
    term: str,
    labels: dict[str, str],
    threshold: float = 90.0,
) -> tuple[str, float] | None:
    """
    Find the best-matching concept for *term* among the label dictionary.

    Parameters
    ----------
    term:
        The raw query string (need not be pre-normalised; matching is
        case-insensitive).
    labels:
        Mapping of *normalised_label* (lowercase, stripped) → concept_id.
        Both pref_label and alt_labels should be included.
    threshold:
        Minimum ``fuzz.ratio`` score (0–100) required to accept a match.
        Default 90.

    Returns
    -------
    (concept_id, score) if a label scores ≥ threshold, else None.
    """
    if not labels:
        return None

    norm_term = term.lower().strip()

    result = process.extractOne(
        norm_term,
        labels.keys(),
        scorer=fuzz.ratio,
        score_cutoff=threshold,
    )

    if result is None:
        return None

    matched_label, score, _ = result
    concept_id = labels[matched_label]
    return concept_id, float(score)
