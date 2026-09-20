---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T01:02:54'
updated: '2026-09-21T01:02:54'
rules: []
---

# src/torsor_helper/coach/hotspots.py

Symbols in `src/torsor_helper/coach/hotspots.py`.

- L11 `_is_git_repo(root: Path)` (function)
- L15 `history_args(history_days: int)` (function) — `git log` bounds shared by churn and temporal coupling. Both used to read
- L22 `_churn(root: Path, history_days: int=365)` (function)
- L29 `_complexity(path: Path)` (function)
- L33 `find_hotspots(root: Path, limit: int=3, history_days: int=365)` (function) — Rank current source files by churn × complexity and surface the top few as
