"""
Concept Resolver — 3-pass term-to-concept resolution.

Pass 1: Exact match (normalised lowercase strip)
Pass 2: Fuzzy match via rapidfuzz.fuzz.ratio at threshold 90
Pass 3: Embedding cosine similarity via sentence-transformers all-MiniLM-L6-v2

Typed degradation:
  resolved        — confident match (exact or fuzzy ≥ 90, or embedding ≥ threshold)
  low_confidence  — embedding match below resolved threshold but above floor
  no_match        — nothing found above any threshold
"""
