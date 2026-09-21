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

# src/torsor_helper/operations/maintenance.py

Symbols in `src/torsor_helper/operations/maintenance.py`.

- L21 `recommend(store, config, context=None, limit=8)` (function)
- L30 `dismiss_recommendation(store, key)` (function)
- L35 `check_staleness(store, config, *, mark=False, unmark=False)` (function) — Detect memory that contradicts current code — dangling [[wikilinks]] and
- L53 `_stale_notes(store)` (function)
- L61 `_note_rel(store, path)` (function)
- L67 `_set_note_status(store, rels: list[str], status: str)` (function) — Rewrite each note's frontmatter `status`, preserving body + other fields
- L84 `stats(store, config)` (function) — What this project actually contains, and whether the derived parts are
- L130 `clean(store, config, *, apply: bool=False, deep: bool=False)` (function) — Reclaim derived and expired torsor artefacts. Dry-run by default: without
- L154 `consolidate(store, config)` (function)
- L181 `_snapshot_complexity(store)` (function) — Refresh the per-file complexity baseline `coach/trend.find_regressions`
