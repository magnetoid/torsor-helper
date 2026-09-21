---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T17:33:16'
updated: '2026-09-21T17:33:16'
rules: []
---

# src/torsor_helper/search.py

Symbols in `src/torsor_helper/search.py`.

- L19 `_importance(tier: Tier, access_count: int, floors: dict[str, float])` (function) — Recall-frequency multiplier in [floor, 1.0]. access_count=0 → floor (no
- L29 `_unit_vectors(vec_by_path)` (function) — Pre-normalize once. Cosine between unit vectors is a plain dot product,
- L41 `_mmr_order(hits, vec_by_path, lam: float)` (function) — Reorder relevance-sorted hits by Maximal Marginal Relevance so near-
- L69 `hybrid_search(conn, embedder, config, query, *, limit=8, max_tokens=1500, type_=None, kind=None, include_superseded=False, symbol=None)` (function)
