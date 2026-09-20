---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/guard.py

Symbols in `src/torsor_helper/guard.py`.

- L14 `load_rules_by_note(store: Store)` (function) — (note path, note title, its rules) for every ADR / system-patterns note
- L46 `load_rules(store: Store)` (function)
- L50 `_forbid_import(relpath: str, text: str, rule: Rule)` (function)
- L85 `_forbid_import_specifiers(relpath: str, text: str, rule: Rule)` (function) — Non-Python: match the rule's target as a prefix of the import specifier
- L101 `_imported_modules(tree: ast.Module, relpath: str)` (function) — All imported module strings (absolute dotted form, relative imports
- L119 `_require_import(relpath: str, text: str, rule: Rule)` (function) — Mandatory-seam check: emit ONE file-level violation when a required import
- L133 `_forbid_layer_import(relpath: str, text: str, rule: Rule)` (function) — Layering check: forbid importing any module whose dotted path matches the
- L163 `_forbid_pattern(relpath: str, text: str, rule: Rule)` (function)
- L175 `_violation(rule: Rule, relpath: str, line: int, default_msg: str)` (function)
- L186 `strict_failures(violations, threshold: str | None=None)` (function) — Violations that should fail --strict: all of them when threshold is None
- L203 `violations_for_file(relpath: str, text: str, rule: Rule)` (function)
- L210 `check_drift(store: Store, files)` (function)
