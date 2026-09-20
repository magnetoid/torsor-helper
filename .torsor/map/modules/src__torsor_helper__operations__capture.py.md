---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/operations/capture.py

Symbols in `src/torsor_helper/operations/capture.py`.

- L21 `_capture_state_path(store)` (function)
- L27 `_load_capture_state(store)` (function)
- L34 `_save_capture_state(store, data: dict)` (function)
- L39 `_op_totals(store)` (function)
- L48 `_op_delta(store, snapshot: dict)` (function) — Per-op hit increase since the last snapshot — a best-effort, deterministic
- L57 `_adrs_between(store, prev: int, cur: int)` (function)
- L67 `_read_md_section(text: str, header: str)` (function) — Body under a `## header` up to the next `## ` (or EOF). Empty when absent.
- L76 `_find_file_paths(obj)` (function) — Recursively collect `file_path` string values from a parsed transcript
- L91 `_transcript_digest(transcript_path)` (function)
- L109 `auto_handoff(store, config, *, session_id=None, transcript_path=None)` (function) — Write a deterministic end-of-session handoff (no LLM) from git history +
- L168 `on_commit(store, config)` (function) — Post-commit hook core: partial-map the just-committed source files (the
