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

# src/torsor_helper/coach/staleness.py

Symbols in `src/torsor_helper/coach/staleness.py`.

- L27 `_rel(store: Store, path)` (function)
- L34 `check_dangling_links(store: Store)` (function) — Notes whose [[wikilink]] points to a note that no longer exists — the
- L58 `check_ambiguous_links(store: Store)` (function) — Notes whose [[wikilink]] could mean more than one note.
- L89 `check_path_refs(store: Store)` (function) — Notes citing a repo-relative source path that no longer exists on disk.
- L117 `run_staleness(store: Store)` (function)
