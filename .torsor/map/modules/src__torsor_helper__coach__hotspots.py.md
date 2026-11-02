---
type: map
status: derived
tags:
- map
links: []
created: '2026-11-02T02:18:30'
updated: '2026-11-02T02:18:30'
rules: []
---

# src/torsor_helper/coach/hotspots.py

Symbols in `src/torsor_helper/coach/hotspots.py`.

- L12 `_is_git_repo(root: Path)` (function)
- L16 `history_args(history_days: int)` (function) — `git log` bounds shared by churn and temporal coupling. Both used to read
- L23 `_churn(root: Path, history_days: int=365)` (function)
- L31 `_complexity(path: Path)` (function)
- L46 `complexity_bound(path: Path, text: str)` (function) — An upper bound on `languages.complexity(path)`, without parsing. Infinite
- L55 `_score_all(present)` (function)
- L64 `_top_scored(present, limit: int)` (function) — The same top `limit` as _score_all, parsing only files that can still
- L96 `find_hotspots(root: Path, limit: int=3, history_days: int=365, *, prune: bool=True)` (function) — Rank current source files by churn × complexity and surface the top few as
