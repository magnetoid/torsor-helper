---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T17:40:34'
updated: '2026-09-21T17:40:34'
rules: []
---

# src/torsor_helper/coach/report.py

Symbols in `src/torsor_helper/coach/report.py`.

- L14 `_coach_state_path(store)` (function)
- L19 `_phantom_dep_recs(store: Store)` (function) — Advisory: imports across the repo that resolve to no known package.
- L37 `assemble(store: Store, config, context=None, limit: int=8, conn=None, embedder=None)` (function)
- L87 `_resolved_rec(keys: list[str])` (function) — What got fixed since last time, as one line.
- L105 `_escalate(rec: Recommendation, state: CoachState)` (function) — Say how long an important recommendation has been open.
- L119 `session_digest(store: Store, limit: int=3)` (function) — Read-only hygiene digest for session start: the index-free checks
