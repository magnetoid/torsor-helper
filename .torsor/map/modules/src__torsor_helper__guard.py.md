---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T15:38:11'
updated: '2026-09-04T15:38:11'
---

# src/torsor_helper/guard.py

Symbols in `src/torsor_helper/guard.py`.

- L13 `load_rules_by_note(store: Store)` (function) — (note path, note title, its rules) for every ADR / system-patterns note
- L45 `load_rules(store: Store)` (function)
- L49 `_forbid_import(relpath: str, text: str, rule: Rule)` (function)
- L84 `_forbid_import_specifiers(relpath: str, text: str, rule: Rule)` (function) — Non-Python: match the rule's target as a prefix of the import specifier
- L100 `_imported_modules(tree: ast.Module, relpath: str)` (function) — All imported module strings (absolute dotted form, relative imports
- L118 `_require_import(relpath: str, text: str, rule: Rule)` (function) — Mandatory-seam check: emit ONE file-level violation when a required import
- L132 `_forbid_layer_import(relpath: str, text: str, rule: Rule)` (function) — Layering check: forbid importing any module whose dotted path matches the
- L162 `_forbid_pattern(relpath: str, text: str, rule: Rule)` (function)
- L174 `_violation(rule: Rule, relpath: str, line: int, default_msg: str)` (function)
- L185 `strict_failures(violations, threshold: str | None=None)` (function) — Violations that should fail --strict: all of them when threshold is None
- L202 `violations_for_file(relpath: str, text: str, rule: Rule)` (function)
- L209 `check_drift(store: Store, files)` (function)
