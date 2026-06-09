"""
Embedding-based concept resolution using sentence-transformers.

Model: all-MiniLM-L6-v2 (384-dimensional, fast, good semantic coverage)

API
---
precompute_embeddings(concepts) -> tuple[np.ndarray, list[str]]
    Build a corpus matrix of concept embeddings.  Encodes pref_label + all
    alt_labels as individual rows so every surface form has an embedding entry.
    Returns (corpus_matrix, concept_ids_parallel_list).

cosine_search(query_embed, corpus, threshold) -> list[tuple[int, float]]
    Return (index, score) pairs for every corpus row whose cosine similarity
    to query_embed is >= threshold, sorted descending by score.

get_model() -> SentenceTransformer
    Lazy singleton — loads the model on first call, cached thereafter.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

import numpy as np

from app.ontology.concepts import Concept

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"


def embeddings_available() -> bool:
    """True if the optional sentence-transformers backend can be imported.

    On size-constrained deployments (e.g. Vercel Lambda's 500 MB limit) the
    heavyweight torch/sentence-transformers stack is omitted.  Callers use this
    to skip the embedding pass and fall back to fuzzy / keyword matching.
    """
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


@functools.lru_cache(maxsize=1)
def get_model() -> "SentenceTransformer":
    """
    Load and cache the sentence-transformer model.

    The model is loaded once on first call.  Subsequent calls return the
    cached instance.  On a cold start this typically takes 3–15 s depending
    on hardware; subsequent calls are instantaneous.

    Raises
    ------
    ImportError
        If the optional ``sentence-transformers`` dependency is not installed.
        Callers should gate on :func:`embeddings_available` first.
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(_MODEL_NAME)


def precompute_embeddings(
    concepts: list[Concept],
) -> tuple[np.ndarray, list[str]]:
    """
    Pre-compute a dense embedding matrix for all concept surface forms.

    For each Concept we encode:
      - pref_label
      - every entry in alt_labels

    Each encoded string maps to the parent concept_id, so the returned
    concept_ids list is parallel to the rows of the corpus matrix.

    Parameters
    ----------
    concepts:
        List of Concept objects from the catalog.

    Returns
    -------
    corpus : np.ndarray of shape (N, 384)
        Stacked embeddings for all surface forms.  Empty (shape (0, 384)) when
        the optional sentence-transformers backend is unavailable, in which case
        the resolver's embedding pass is skipped.
    concept_ids : list[str] of length N
        concept_ids[i] is the concept_id for corpus[i].
    """
    if not embeddings_available():
        return np.empty((0, 384), dtype=np.float32), []

    model = get_model()

    texts: list[str] = []
    concept_ids: list[str] = []

    for concept in concepts:
        # Always include the canonical label
        texts.append(concept.pref_label)
        concept_ids.append(concept.id)

        # Include every synonym
        for alt in concept.alt_labels:
            texts.append(alt)
            concept_ids.append(concept.id)

    if not texts:
        return np.empty((0, 384), dtype=np.float32), []

    corpus: np.ndarray = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        normalize_embeddings=True,  # L2-normalise so dot product == cosine sim
        convert_to_numpy=True,
    )

    return corpus, concept_ids


def cosine_search(
    query_embed: np.ndarray,
    corpus: np.ndarray,
    threshold: float = 0.5,
) -> list[tuple[int, float]]:
    """
    Return corpus indices whose cosine similarity to query_embed is >= threshold.

    Because both query and corpus rows are L2-normalised in precompute_embeddings
    (and the caller should also normalise the query), the dot product equals the
    cosine similarity.

    Parameters
    ----------
    query_embed:
        1-D array of shape (D,) — the query embedding.  Should be L2-normalised.
    corpus:
        2-D array of shape (N, D) — pre-computed, L2-normalised corpus embeddings.
    threshold:
        Minimum cosine similarity [0, 1] to include in results.

    Returns
    -------
    List of (index, score) tuples sorted by descending score, filtered to
    those with score >= threshold.
    """
    if corpus.shape[0] == 0:
        return []

    # Ensure query is 1-D and normalised
    q = np.asarray(query_embed, dtype=np.float32).reshape(-1)
    norm = np.linalg.norm(q)
    if norm > 0:
        q = q / norm

    scores: np.ndarray = corpus @ q  # shape (N,)

    results: list[tuple[int, float]] = [
        (int(i), float(scores[i]))
        for i in range(len(scores))
        if scores[i] >= threshold
    ]
    results.sort(key=lambda x: x[1], reverse=True)
    return results
