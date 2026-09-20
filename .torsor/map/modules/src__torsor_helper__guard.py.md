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

# src/torsor_helper/guard.py

Symbols in `src/torsor_helper/guard.py`.

- L13 `load_rules_by_note(store: Store)` (function) — (note path, note title, its rules) for every ADR / system-patterns note
- L48 `_scope_regex(scope: str)` (function) — Translate a scope glob to a regex with path-aware semantics.
- L88 `scope_matches(relpath: str, scope: str)` (function) — Does `relpath` fall inside `scope`?
- L103 `load_rules(store: Store)` (function)
- L107 `_forbid_import(relpath: str, text: str, rule: Rule)` (function)
- L142 `_forbid_import_specifiers(relpath: str, text: str, rule: Rule)` (function) — Non-Python: match the rule's target as a prefix of the import specifier
- L158 `_imported_modules(tree: ast.Module, relpath: str)` (function) — All imported module strings (absolute dotted form, relative imports
- L176 `_require_import(relpath: str, text: str, rule: Rule)` (function) — Mandatory-seam check: emit ONE file-level violation when a required import
- L190 `_forbid_layer_import(relpath: str, text: str, rule: Rule)` (function) — Layering check: forbid importing any module whose dotted path matches the
- L220 `_forbid_pattern(relpath: str, text: str, rule: Rule)` (function)
- L232 `_violation(rule: Rule, relpath: str, line: int, default_msg: str)` (function)
- L244 `strict_failures(violations, threshold: str | None=None)` (function) — Violations that should fail --strict: all of them when threshold is None
- L261 `violations_for_file(relpath: str, text: str, rule: Rule)` (function)
- L268 `check_drift(store: Store, files)` (function)
