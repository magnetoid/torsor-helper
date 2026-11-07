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

# src/torsor_helper/guard.py

Symbols in `src/torsor_helper/guard.py`.

- L16 `load_rules_by_note(store: Store)` (function) — (note path, note title, its rules) for every ADR / system-patterns note
- L54 `check_cycles(store: Store, rules: list[Rule])` (function) — Import cycles among the modules a `forbid_cycle` rule covers.
- L108 `_in_scope(module: str, prefix: str)` (function)
- L112 `_cycles(graph: dict[str, set[str]])` (function) — One representative cycle per strongly connected component, in a stable
- L163 `_scope_regex(scope: str)` (function)
- L169 `rule_applies(relpath: str, rule)` (function) — Is this file inside the rule's scope and outside its exception?
- L176 `scope_matches(relpath: str, scope: str)` (function) — Does `relpath` fall inside `scope`?
- L191 `load_rules(store: Store)` (function)
- L195 `_forbid_import(relpath: str, text: str, rule: Rule)` (function)
- L229 `_forbid_import_specifiers(relpath: str, text: str, rule: Rule)` (function) — Non-Python: match the rule's target as a prefix of the import specifier
- L245 `_imported_modules(tree: ast.Module, relpath: str)` (function) — All imported module strings (absolute dotted form, relative imports
- L263 `_require_import(relpath: str, text: str, rule: Rule)` (function) — Mandatory-seam check: emit ONE file-level violation when a required import
- L276 `_forbid_layer_import(relpath: str, text: str, rule: Rule)` (function) — Layering check: forbid importing any module whose dotted path matches the
- L305 `_forbid_pattern(relpath: str, text: str, rule: Rule)` (function)
- L317 `_violation(rule: Rule, relpath: str, line: int, default_msg: str)` (function)
- L329 `strict_failures(violations, threshold: str | None=None)` (function) — Violations that should fail --strict: all of them when threshold is None
- L346 `violations_for_file(relpath: str, text: str, rule: Rule)` (function)
- L353 `check_drift(store: Store, files)` (function)
