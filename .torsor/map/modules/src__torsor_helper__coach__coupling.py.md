---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T05:04:01'
updated: '2026-09-04T05:04:01'
---

# src/torsor_helper/coach/coupling.py

Symbols in `src/torsor_helper/coach/coupling.py`.

- L14 `_commits(root: Path)` (function) — Each commit as the set of *.py files it touched (via git log --name-only).
- L37 `find_coupling(root: Path, min_commits: int=3, max_files: int=40, threshold: float=0.6)` (function) — Pairs of files that change together far more often than chance.
- L69 `find_coupling_recs(root: Path, conn, limit: int=3)` (function) — Coupling recs for the top co-changed pairs NOT already linked by an import
