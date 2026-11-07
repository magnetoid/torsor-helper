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

# src/torsor_helper/coach/report.py

Symbols in `src/torsor_helper/coach/report.py`.

- L12 `_coach_state_path(store)` (function)
- L17 `_phantom_dep_recs(store: Store)` (function) — Advisory: imports across the repo that resolve to no known package.
- L35 `assemble(store: Store, config, context=None, limit: int=8, conn=None, embedder=None)` (function)
- L92 `_resolved_rec(keys: list[str])` (function) — What got fixed since last time, as one line.
- L110 `_escalate(rec: Recommendation, state: CoachState)` (function) — Say how long an important recommendation has been open.
- L124 `session_digest(store: Store, limit: int=3)` (function) — Read-only hygiene digest for session start: the index-free checks
