---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T05:04:02'
updated: '2026-09-04T05:04:02'
---

# src/torsor_helper/guard.py

Symbols in `src/torsor_helper/guard.py`.

- L13 `load_rules_by_note(store: Store)` (function) — (note path, note title, its rules) for every ADR / system-patterns note
- L45 `load_rules(store: Store)` (function)
- L49 `_forbid_import(relpath: str, text: str, rule: Rule)` (function)
- L82 `_imported_modules(tree: ast.Module, relpath: str)` (function) — All imported module strings (absolute dotted form, relative imports
- L100 `_require_import(relpath: str, text: str, rule: Rule)` (function) — Mandatory-seam check: emit ONE file-level violation when a required import
- L114 `_forbid_layer_import(relpath: str, text: str, rule: Rule)` (function) — Layering check: forbid importing any module whose dotted path matches the
- L144 `_forbid_pattern(relpath: str, text: str, rule: Rule)` (function)
- L156 `_violation(rule: Rule, relpath: str, line: int, default_msg: str)` (function)
- L167 `strict_failures(violations, threshold: str | None=None)` (function) — Violations that should fail --strict: all of them when threshold is None
- L184 `violations_for_file(relpath: str, text: str, rule: Rule)` (function)
- L191 `check_drift(store: Store, files)` (function)
