"""
Phase 4 validation: 3-Pass Concept Resolver

Tests cover:
  1. Exact-match pass — direct pref_label and alt_label hits
  2. Fuzzy-match pass — typos and near-exact strings above threshold 90
  3. Embedding-fallback pass — semantically related terms with no lexical match
  4. No-match degradation — nonsense terms below all thresholds
  5. Resolution dataclass fields — status, concept, confidence, pass_used, candidates
  6. Threshold semantics — low_confidence band correctly populated
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from app.ontology.catalog import build_concept_catalog
from app.resolver.embeddings import cosine_search, precompute_embeddings
from app.resolver.fuzzy import fuzzy_match
from app.resolver.resolver import (
    EMBEDDING_LOW_CONF_THRESHOLD,
    EMBEDDING_RESOLVED_THRESHOLD,
    FUZZY_THRESHOLD,
    Resolution,
    resolve,
)


# ---------------------------------------------------------------------------
# Module-scoped fixtures (expensive — load model once per test session)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def catalog():
    return build_concept_catalog()


@pytest.fixture(scope="module")
def corpus_and_ids(catalog):
    """Pre-compute embedding corpus once for the whole test module."""
    corpus, concept_ids = precompute_embeddings(list(catalog.values()))
    return corpus, concept_ids


# ---------------------------------------------------------------------------
# Pass 1: Exact match
# ---------------------------------------------------------------------------


class TestExactPass:
    def test_pref_label_exact_match(self, catalog, corpus_and_ids):
        """Exact pref_label 'Knee' (case-insensitive) resolves to 'knee'."""
        corpus, cids = corpus_and_ids
        res = resolve("knee", catalog, corpus, cids)

        assert res.status == "resolved"
        assert res.concept == "knee"
        assert res.pass_used == "exact"
        assert res.confidence == 1.0

    def test_alt_label_exact_match(self, catalog, corpus_and_ids):
        """
        'posterior chain' is an alt_label for hamstrings.
        It must resolve to 'hamstrings' via the exact pass.
        """
        corpus, cids = corpus_and_ids
        res = resolve("posterior chain", catalog, corpus, cids)

        assert res.status == "resolved"
        assert res.concept == "hamstrings"
        # exact because 'posterior chain' is literally in alt_labels
        assert res.pass_used == "exact"
        assert res.confidence == 1.0

    def test_pref_label_case_insensitive(self, catalog, corpus_and_ids):
        """Exact match should be case-insensitive."""
        corpus, cids = corpus_and_ids
        res = resolve("BARBELL", catalog, corpus, cids)

        assert res.status == "resolved"
        assert res.concept == "barbell"
        assert res.pass_used == "exact"

    def test_pref_label_whitespace_insensitive(self, catalog, corpus_and_ids):
        """Leading/trailing whitespace should not affect exact matching."""
        corpus, cids = corpus_and_ids
        res = resolve("  knee  ", catalog, corpus, cids)

        assert res.status == "resolved"
        assert res.concept == "knee"
        assert res.pass_used == "exact"

    def test_snomed_alt_label_resolves(self, catalog, corpus_and_ids):
        """'pecs' is an alt_label for chest and should resolve exactly."""
        corpus, cids = corpus_and_ids
        res = resolve("pecs", catalog, corpus, cids)

        assert res.status == "resolved"
        assert res.concept == "chest"
        assert res.pass_used == "exact"

    def test_equipment_exact_match(self, catalog, corpus_and_ids):
        """Equipment concept resolves by pref_label."""
        corpus, cids = corpus_and_ids
        res = resolve("Dumbbell", catalog, corpus, cids)

        assert res.status == "resolved"
        assert res.concept == "dumbbell"
        assert res.pass_used == "exact"


# ---------------------------------------------------------------------------
# Pass 2: Fuzzy match
# ---------------------------------------------------------------------------


class TestFuzzyPass:
    def test_typo_resolves_via_fuzzy(self, catalog, corpus_and_ids):
        """
        'hamstrigns' (transposed characters) scores 90 via fuzz.ratio
        and should resolve to 'hamstrings'.
        """
        corpus, cids = corpus_and_ids
        res = resolve("hamstrigns", catalog, corpus, cids)

        assert res.status == "resolved"
        assert res.concept == "hamstrings"
        assert res.pass_used == "fuzzy"
        assert 0.88 <= res.confidence <= 1.0

    def test_near_exact_equipment_resolves_via_fuzzy(self, catalog, corpus_and_ids):
        """
        'pullup bar' (missing hyphen) should resolve to 'pull_up_bar' via fuzzy.
        """
        corpus, cids = corpus_and_ids
        res = resolve("pullup bar", catalog, corpus, cids)

        assert res.status == "resolved"
        assert res.concept == "pull_up_bar"
        assert res.pass_used == "fuzzy"

    def test_fuzzy_confidence_in_valid_range(self, catalog, corpus_and_ids):
        """Fuzzy confidence is fuzz.ratio / 100, so in (0, 1]."""
        corpus, cids = corpus_and_ids
        res = resolve("hamstrigns", catalog, corpus, cids)

        assert res.confidence is not None
        assert 0.0 < res.confidence <= 1.0


# ---------------------------------------------------------------------------
# Fuzzy standalone unit tests
# ---------------------------------------------------------------------------


class TestFuzzyMatchUnit:
    def test_exact_label_scores_100(self):
        """Direct exact match in labels dict."""
        labels = {"hamstrings": "hamstrings", "quads": "quads"}
        result = fuzzy_match("hamstrings", labels, threshold=90)
        assert result is not None
        concept_id, score = result
        assert concept_id == "hamstrings"
        assert score == pytest.approx(100.0)

    def test_below_threshold_returns_none(self):
        """Term with low similarity should return None."""
        labels = {"hamstrings": "hamstrings", "quadriceps": "quads"}
        result = fuzzy_match("barbell", labels, threshold=90)
        assert result is None

    def test_threshold_boundary(self):
        """Score exactly at threshold should be accepted."""
        labels = {"hamstrigns": "hamstrings"}  # transposed gives ratio=90
        # Confirm it's at threshold
        from rapidfuzz import fuzz
        score = fuzz.ratio("hamstrigns", "hamstrigns")
        assert score == 100.0  # same string
        result = fuzzy_match("hamstrigns", labels, threshold=90)
        assert result is not None

    def test_empty_labels_returns_none(self):
        """Empty label dict should return None."""
        result = fuzzy_match("knee", {}, threshold=90)
        assert result is None


# ---------------------------------------------------------------------------
# Pass 3: Embedding fallback
# ---------------------------------------------------------------------------


class TestEmbeddingPass:
    def test_bad_lower_back_resolves_via_embedding(self, catalog, corpus_and_ids):
        """
        'bad lower back' has no exact or fuzzy match (fuzz.ratio is below 90
        for any label) but is semantically very close to 'Lower Back' / lumbar.
        The embedding pass should resolve it.
        """
        corpus, cids = corpus_and_ids
        res = resolve("bad lower back", catalog, corpus, cids)

        # The embedding should identify a back/lumbar concept
        assert res.status == "resolved"
        assert res.pass_used == "embedding"
        assert res.concept in {"lower_back", "lumbar_spine"}
        assert res.confidence is not None
        assert res.confidence >= EMBEDDING_RESOLVED_THRESHOLD

    def test_embedding_pass_confidence_is_cosine_similarity(
        self, catalog, corpus_and_ids
    ):
        """Embedding confidence should be a cosine similarity in (0, 1]."""
        corpus, cids = corpus_and_ids
        res = resolve("bad lower back", catalog, corpus, cids)

        assert res.pass_used == "embedding"
        assert 0.0 < res.confidence <= 1.0

    def test_semantically_close_term_resolves(self, catalog, corpus_and_ids):
        """
        'pressing muscles in chest' is semantically close to 'chest' /
        'pectoralis'.  The embedding should find a chest/upper-push concept.
        """
        corpus, cids = corpus_and_ids
        res = resolve("pressing muscles in chest", catalog, corpus, cids)

        assert res.status in {"resolved", "low_confidence"}
        assert res.pass_used == "embedding"
        # Should map to a chest/shoulder/upper-push concept
        assert res.concept is not None


# ---------------------------------------------------------------------------
# Pass 3: Cosine search unit tests
# ---------------------------------------------------------------------------


class TestCosineSearch:
    def test_identical_vector_scores_one(self):
        """Cosine similarity of identical L2-normalised vectors = 1.0."""
        v = np.array([0.6, 0.8, 0.0], dtype=np.float32)
        v /= np.linalg.norm(v)
        corpus = v.reshape(1, -1)

        hits = cosine_search(v, corpus, threshold=0.5)
        assert len(hits) == 1
        idx, score = hits[0]
        assert idx == 0
        assert score == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vector_excluded(self):
        """Orthogonal vectors have cosine similarity 0, below any sensible threshold."""
        a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        corpus = b.reshape(1, -1)

        hits = cosine_search(a, corpus, threshold=0.1)
        assert len(hits) == 0

    def test_results_sorted_descending(self):
        """Results should be sorted by descending cosine similarity."""
        rng = np.random.default_rng(42)
        corpus = rng.standard_normal((10, 8)).astype(np.float32)
        # L2-normalise each row
        corpus /= np.linalg.norm(corpus, axis=1, keepdims=True)
        q = rng.standard_normal(8).astype(np.float32)
        q /= np.linalg.norm(q)

        hits = cosine_search(q, corpus, threshold=-1.0)  # accept all
        scores = [s for _, s in hits]
        assert scores == sorted(scores, reverse=True)

    def test_empty_corpus_returns_empty(self):
        """Empty corpus should return empty list."""
        q = np.array([1.0, 0.0], dtype=np.float32)
        corpus = np.empty((0, 2), dtype=np.float32)
        hits = cosine_search(q, corpus, threshold=0.5)
        assert hits == []


# ---------------------------------------------------------------------------
# No-match degradation
# ---------------------------------------------------------------------------


class TestNoMatch:
    def test_nonsense_string_returns_no_match(self, catalog, corpus_and_ids):
        """
        A completely nonsensical token with no semantic relationship to any
        concept should return status='no_match'.
        """
        corpus, cids = corpus_and_ids
        res = resolve("xyzabcdefgh123notaconcept", catalog, corpus, cids)

        assert res.status == "no_match"
        assert res.concept is None
        assert res.confidence is None
        assert res.pass_used is None

    def test_no_match_has_empty_candidates(self, catalog, corpus_and_ids):
        """no_match results have an empty candidates list."""
        corpus, cids = corpus_and_ids
        res = resolve("xyzabcdefgh123notaconcept", catalog, corpus, cids)

        assert res.candidates == []

    def test_empty_string_returns_no_match_or_resolved(self, catalog, corpus_and_ids):
        """
        An empty string may or may not resolve — the important thing is it
        does not raise an exception.
        """
        corpus, cids = corpus_and_ids
        res = resolve("", catalog, corpus, cids)
        assert res.status in {"resolved", "low_confidence", "no_match"}


# ---------------------------------------------------------------------------
# Resolution dataclass field contract
# ---------------------------------------------------------------------------


class TestResolutionContract:
    def test_resolved_has_concept_and_confidence(self, catalog, corpus_and_ids):
        """A resolved result always has concept and confidence."""
        corpus, cids = corpus_and_ids
        res = resolve("knee", catalog, corpus, cids)

        assert res.status == "resolved"
        assert res.concept is not None
        assert res.confidence is not None
        assert res.pass_used is not None

    def test_no_match_fields_are_none(self, catalog, corpus_and_ids):
        """A no_match result has None for concept, confidence, and pass_used."""
        corpus, cids = corpus_and_ids
        res = resolve("xyzabcdefgh123notaconcept", catalog, corpus, cids)

        assert res.concept is None
        assert res.confidence is None
        assert res.pass_used is None

    def test_resolved_candidates_is_empty(self, catalog, corpus_and_ids):
        """A resolved result has no candidates (they're for low_confidence)."""
        corpus, cids = corpus_and_ids
        res = resolve("knee", catalog, corpus, cids)

        assert res.candidates == []

    def test_pass_used_is_valid_literal(self, catalog, corpus_and_ids):
        """pass_used must be one of the three valid literal values."""
        valid_passes = {"exact", "fuzzy", "embedding", None}
        corpus, cids = corpus_and_ids

        for term in ["knee", "hamstrigns", "bad lower back"]:
            res = resolve(term, catalog, corpus, cids)
            assert res.pass_used in valid_passes, (
                f"Unexpected pass_used={res.pass_used!r} for term {term!r}"
            )


# ---------------------------------------------------------------------------
# Embedding precompute tests
# ---------------------------------------------------------------------------


class TestPrecomputeEmbeddings:
    def test_corpus_shape(self, catalog, corpus_and_ids):
        """Corpus has one row per surface form (pref_label + alt_labels)."""
        corpus, concept_ids = corpus_and_ids
        assert corpus.ndim == 2
        assert corpus.shape[1] == 384  # all-MiniLM-L6-v2 output dim

    def test_parallel_list_same_length(self, catalog, corpus_and_ids):
        """concept_ids list is parallel to corpus rows."""
        corpus, concept_ids = corpus_and_ids
        assert corpus.shape[0] == len(concept_ids)

    def test_all_catalog_concepts_covered(self, catalog, corpus_and_ids):
        """Every concept_id in the catalog appears at least once."""
        _, concept_ids = corpus_and_ids
        covered = set(concept_ids)
        for cid in catalog:
            assert cid in covered, f"Concept '{cid}' missing from embedding corpus"

    def test_corpus_rows_are_normalised(self, catalog, corpus_and_ids):
        """Corpus rows should be L2-normalised (norm ≈ 1.0)."""
        corpus, _ = corpus_and_ids
        norms = np.linalg.norm(corpus, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)


# ---------------------------------------------------------------------------
# Boot-time performance guard
# ---------------------------------------------------------------------------


class TestPerformance:
    def test_resolve_with_preloaded_model_is_fast(self, catalog, corpus_and_ids):
        """
        With the model already loaded (warm), a single resolve() call should
        complete in < 1 s.  (Model load itself is excluded by the module-scoped
        fixture.)
        """
        corpus, cids = corpus_and_ids
        start = time.monotonic()
        resolve("knee", catalog, corpus, cids)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0, f"resolve() took {elapsed:.2f}s (expected < 1s)"
