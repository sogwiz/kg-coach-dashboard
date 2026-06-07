"""
Tests for the Copilot knowledge corpus (RAG enhancement).

Covers: corpus loads with well-formed docs, embedding retrieval surfaces the
right doc, the keyword fallback works without embeddings, and empty queries
degrade cleanly.
"""

from __future__ import annotations

import os

from app.copilot.rag import load_corpus, search_corpus


def test_corpus_loads_well_formed():
    docs = load_corpus()
    assert len(docs) >= 8
    for d in docs:
        assert {"id", "title", "category", "content"} <= set(d.keys())
        assert d["content"].strip()


def test_embedding_search_finds_zone2():
    r = search_corpus("what is zone 2 training for endurance", k=3)
    assert r["count"] >= 1
    titles = [x["title"].lower() for x in r["results"]]
    assert any("zone 2" in t for t in titles)
    # top hit should be the most relevant doc
    assert "zone 2" in r["results"][0]["title"].lower()


def test_keyword_fallback_without_embeddings():
    os.environ["RAG_EMBEDDINGS"] = "off"
    try:
        r = search_corpus("ketogenic diet low carb", k=3)
        assert r["method"] == "keyword"
        assert any("keto" in x["title"].lower() for x in r["results"])
    finally:
        os.environ.pop("RAG_EMBEDDINGS", None)


def test_empty_query_returns_nothing():
    r = search_corpus("", k=3)
    assert r["count"] == 0
    assert r["results"] == []
