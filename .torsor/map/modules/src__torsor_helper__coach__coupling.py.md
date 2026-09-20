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

# src/torsor_helper/coach/coupling.py

Symbols in `src/torsor_helper/coach/coupling.py`.

- L13 `_commits(root: Path, history_days: int=365)` (function) — Each commit as the set of source files it touched (via git log --name-only).
- L34 `find_coupling(root: Path, min_commits: int=3, max_files: int=40, threshold: float=0.6, history_days: int=365)` (function) — Pairs of files that change together far more often than chance.
- L66 `find_coupling_recs(root: Path, conn, limit: int=3, history_days: int=365)` (function) — Coupling recs for the top co-changed pairs NOT already linked by an import
