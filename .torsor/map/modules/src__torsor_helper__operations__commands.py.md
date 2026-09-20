---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/operations/commands.py

Symbols in `src/torsor_helper/operations/commands.py`.

- L19 `list_commands(store: Store)` (function) — The recorded project commands, parsed from .torsor/commands.md.
- L30 `record_command(store: Store, name: str, command: str, note: str='')` (function) — Record/update a named project command so it's never re-derived. Persists to
- L49 `run_command(store: Store, name: str)` (function) — Execute a recorded command (returns CompletedProcess, or None if unknown).
- L58 `recipes(store: Store, limit: int=10)` (function) — The most-repeated deterministic lookups — what the agent does over and over,
