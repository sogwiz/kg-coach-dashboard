"""
Corpus RAG — retrieval over a small program / diet / recovery / competition
knowledge corpus for OPEN-ENDED Copilot questions ("what is Zone 2?",
"explain 5x5", "is keto good for HYROX?").

This is the *enhancement* half of our retrieval story:
  - Member questions      → KG2 graph/tool retrieval (the other agent tools)
  - Generic knowledge     → this corpus
  - Safety / selection    → deterministic graph traversal (NEVER RAG)

Retrieval is cosine over MiniLM embeddings by default (the model is already
loaded for the concept resolver, so this is essentially free), with a keyword
full-text fallback. Embeddings are pluggable: set RAG_EMBEDDINGS=off to force
the keyword path (no embedding provider needed).

Corpus lives in data/corpus.json (Document-shaped records).
"""

from __future__ import annotations

import functools
import json
import os
import re
from pathlib import Path

import numpy as np

from app.data.paths import find_data_dir

# Corpus lives in the seed data dir (resolved robustly for local + Vercel).
_CORPUS_PATH = find_data_dir() / "corpus.json"


@functools.lru_cache(maxsize=1)
def load_corpus() -> list[dict]:
    """Load and cache the knowledge corpus. Returns [] if the file is missing."""
    try:
        return json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _doc_text(doc: dict) -> str:
    """Flatten a doc into the text we embed / keyword-match against."""
    tags = ", ".join(doc.get("tags", []))
    return f"{doc.get('title', '')}. {tags}. {doc.get('content', '')}"


@functools.lru_cache(maxsize=1)
def _corpus_matrix() -> "np.ndarray | None":
    """Embed every corpus doc once (cached). None if the corpus or model is unavailable."""
    docs = load_corpus()
    if not docs:
        return None
    from app.resolver.embeddings import get_model

    model = get_model()
    return model.encode(
        [_doc_text(d) for d in docs],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )


def _embeddings_enabled() -> bool:
    return os.environ.get("RAG_EMBEDDINGS", "on").strip().lower() not in ("off", "0", "false")


def _keyword_search(query: str, docs: list[dict], k: int) -> list[tuple[dict, float]]:
    """Full-text fallback: score by query-term frequency across title/tags/content."""
    terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
    scored: list[tuple[float, dict]] = []
    for d in docs:
        hay = _doc_text(d).lower()
        score = float(sum(hay.count(t) for t in terms))
        if score > 0:
            scored.append((score, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [(d, s) for s, d in scored[:k]]


def search_corpus(query: str, k: int = 3) -> dict:
    """
    Retrieve the top-k corpus docs most relevant to `query`.

    Returns a dict: {query, method ("embedding"|"keyword"|"none"), count,
    results:[{id, title, category, source, score, content}]}. The agent grounds
    its answer in the returned content and cites the title.
    """
    q = (query or "").strip()
    docs = load_corpus()
    if not q or not docs:
        return {"query": q, "method": "none", "count": 0, "results": []}

    hits: list[tuple[dict, float]] = []
    method = "keyword"

    if _embeddings_enabled():
        try:
            mat = _corpus_matrix()
            if mat is not None:
                from app.resolver.embeddings import get_model

                qv = get_model().encode(
                    [q], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
                )[0]
                sims = mat @ qv  # cosine (both normalised)
                order = np.argsort(-sims)[:k]
                hits = [(docs[int(i)], float(sims[int(i)])) for i in order]
                method = "embedding"
        except Exception:
            hits = []

    if not hits:
        hits = _keyword_search(q, docs, k)
        method = "keyword"

    results = [
        {
            "id": d["id"],
            "title": d["title"],
            "category": d.get("category", ""),
            "source": d.get("source", ""),
            "score": round(s, 3),
            "content": d["content"],
        }
        for d, s in hits
    ]
    return {"query": q, "method": method, "count": len(results), "results": results}
