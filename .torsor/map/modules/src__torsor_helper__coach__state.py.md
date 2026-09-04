---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T05:04:02'
updated: '2026-09-04T05:04:02'
---

# src/torsor_helper/coach/state.py

Symbols in `src/torsor_helper/coach/state.py`.

- L7 `CoachState` (class) — Per-recommendation tracking (dismissed / times_shown), persisted as JSON.
- L13 `__init__(self, path: Path)` (method)
- L22 `_entry(self, key: str)` (method)
- L25 `is_dismissed(self, key: str)` (method)
- L28 `dismiss(self, key: str)` (method)
- L31 `seen(self, key: str)` (method)
- L35 `times_shown(self, key: str)` (method)
- L38 `save(self)` (method)
