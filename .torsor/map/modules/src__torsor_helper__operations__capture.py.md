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

# src/torsor_helper/operations/capture.py

Symbols in `src/torsor_helper/operations/capture.py`.

- L20 `_capture_state_path(store)` (function)
- L26 `_load_capture_state(store)` (function)
- L33 `_save_capture_state(store, data: dict)` (function)
- L38 `_adrs_between(store, prev: int, cur: int)` (function)
- L48 `_read_md_section(text: str, header: str)` (function) — Body under a `## header` up to the next `## ` (or EOF). Empty when absent.
- L57 `_find_file_paths(obj)` (function) — Recursively collect `file_path` string values from a parsed transcript
- L72 `_transcript_digest(transcript_path)` (function)
- L90 `auto_handoff(store, config, *, session_id=None, transcript_path=None)` (function) — Write a deterministic end-of-session handoff (no LLM) from git history +
- L149 `on_commit(store, config)` (function) — Post-commit hook core: partial-map the just-committed source files (the
- L163 `_has_content(store, path)` (function)
