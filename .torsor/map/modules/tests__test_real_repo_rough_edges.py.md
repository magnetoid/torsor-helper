---
type: map
status: derived
tags:
- map
links: []
created: '2026-11-02T02:18:31'
updated: '2026-11-02T02:18:31'
rules: []
---

# tests/test_real_repo_rough_edges.py

Symbols in `tests/test_real_repo_rough_edges.py`.

- L19 `_store(tmp_path)` (function)
- L25 `test_mapping_a_project_with_invalid_escapes_is_silent(tmp_path)` (function) — `map` printed `<unknown>:625: SyntaxWarning: invalid escape sequence '\d'`
- L51 `test_a_nul_byte_does_not_take_the_map_down(tmp_path)` (function) — A regression guard, not a fix. `compile()`'s documented contract raises
- L64 `test_parse_quietly(source)` (function)
- L73 `test_coach_accepts_a_limit_on_the_cli(tmp_path)` (function) — The MCP `recommend` tool takes `limit`; the CLI could never show more than
