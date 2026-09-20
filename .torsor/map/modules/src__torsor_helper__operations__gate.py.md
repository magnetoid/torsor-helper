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

# src/torsor_helper/operations/gate.py

Symbols in `src/torsor_helper/operations/gate.py`.

- L20 `check_drift(store, config, files=None)` (function)
- L26 `new_drift(store, config, files=None)` (function) — Drift beyond the committed baseline — the genuinely-new violations.
- L31 `guard_run(store, config, files=None, *, update_baseline=False, strict=False, severity=None)` (function) — The single guard orchestration both adapters share: check drift, apply
- L45 `check_dependencies(store, config, files=None)` (function) — Flag imports that resolve to no known package (possible slopsquatting).
- L53 `_verify_check(name, ok, status, reasons, *, cap: int=0)` (function) — `count` is the true number of reasons; `reasons` is capped so a gate that
- L60 `_verify_tests(store)` (function) — Run a recorded `test` (or `verify`) command if one exists; skip — never
- L73 `verify(store, config, files=None, *, severity=None, run_tests=False)` (function) — The single deterministic verification gate: guard (new drift) + deps
- L116 `pre_push(store, config)` (function) — Pre-push hook core: advisory guard. Installed only when guard_on_push is
- L125 `_proposed_text(path, tool_name: str, tool_input: dict)` (function) — The file content an Edit/Write *would* produce — reconstructed, never
- L144 `pre_edit(store, config, tool_name, tool_input)` (function) — PreToolUse edit-gate core: run the ADR rules against the *proposed*
