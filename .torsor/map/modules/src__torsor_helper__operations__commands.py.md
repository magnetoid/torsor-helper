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

# src/torsor_helper/operations/commands.py

Symbols in `src/torsor_helper/operations/commands.py`.

- L18 `list_commands(store: Store)` (function) — The recorded project commands, parsed from .torsor/commands.md.
- L29 `record_command(store: Store, name: str, command: str, note: str='')` (function) — Record/update a named project command so it's never re-derived. Persists to
- L48 `run_command(store: Store, name: str)` (function) — Execute a recorded command (returns CompletedProcess, or None if unknown).
