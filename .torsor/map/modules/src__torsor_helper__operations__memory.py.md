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

# src/torsor_helper/operations/memory.py

Symbols in `src/torsor_helper/operations/memory.py`.

- L36 `bootstrap_session(store: Store, config: TorsorConfig, *, max_tokens: int | None=None)` (function)
- L77 `session_start_context(store: Store, config: TorsorConfig, *, how: str='startup')` (function) — The digest the Claude Code SessionStart hook injects. Same composition as
- L103 `_recent_journal(store: Store, max_tokens: int, cpt: int)` (function)
- L121 `recall(store: Store, config: TorsorConfig, query: str, limit: int=8, *, type_: str | None=None, kind: str | None=None, include_superseded: bool=False, symbol: str | None=None)` (function) — Hybrid search across the pyramid, token-budgeted.
- L150 `_passes(note, type_: str | None, kind: str | None, include_superseded: bool, symbol: str | None=None)` (function) — The same filters hybrid_search applies in SQL, for the no-index path.
- L164 `remember(store: Store, content: str, kind: str='observation', links: list[str] | None=None)` (function)
- L168 `update_active(store: Store, focus: str, progress: str, open_questions: str)` (function)
- L182 `record_handoff(store: Store, summary: str, decisions: str='', open_questions: str='', next_steps: str='')` (function)
- L198 `get_intent(store: Store, config: TorsorConfig, topic: str | None=None)` (function)
