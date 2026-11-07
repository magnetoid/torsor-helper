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

# src/torsor_helper/operations/maintenance.py

Symbols in `src/torsor_helper/operations/maintenance.py`.

- L18 `recommend(store, config, context=None, limit=8)` (function)
- L27 `dismiss_recommendation(store, key)` (function)
- L32 `check_staleness(store, config, *, mark=False, unmark=False)` (function) — Detect memory that contradicts current code — dangling [[wikilinks]] and
- L49 `_stale_notes(store)` (function)
- L57 `_note_rel(store, path)` (function)
- L63 `_set_note_status(store, rels: list[str], status: str)` (function) — Rewrite each note's frontmatter `status`, preserving body + other fields
- L80 `stats(store, config)` (function) — What this project actually contains, and whether the derived parts are
- L128 `clean(store, config, *, apply: bool=False, deep: bool=False)` (function) — Reclaim derived and expired torsor artefacts. Dry-run by default: without
