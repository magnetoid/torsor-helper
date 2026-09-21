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

# src/torsor_helper/coach/state.py

Symbols in `src/torsor_helper/coach/state.py`.

- L9 `CoachState` (class) — Per-recommendation tracking, persisted as JSON.
- L22 `__init__(self, path: Path, clock: Callable[[], datetime]=datetime.now)` (method)
- L32 `_entry(self, key: str)` (method)
- L35 `_today(self)` (method)
- L38 `is_dismissed(self, key: str)` (method)
- L41 `dismiss(self, key: str)` (method)
- L44 `seen(self, key: str)` (method)
- L50 `times_shown(self, key: str)` (method)
- L53 `first_seen(self, key: str)` (method)
- L56 `last_shown(self, key: str)` (method)
- L59 `days_open(self, key: str)` (method) — How long this recommendation has been unaddressed, in days. 0 when it
- L71 `resolve_missing(self, present: Iterable[str])` (method) — Keys that were shown before and are not being produced any more — i.e.
- L92 `save(self)` (method)
