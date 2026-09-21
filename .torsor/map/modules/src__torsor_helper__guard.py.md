---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T17:33:16'
updated: '2026-09-21T17:33:16'
rules: []
---

# src/torsor_helper/guard.py

Symbols in `src/torsor_helper/guard.py`.

- L14 `load_rules_by_note(store: Store)` (function) — (note path, note title, its rules) for every ADR / system-patterns note
- L52 `check_cycles(store: Store, rules: list[Rule])` (function) — Import cycles among the modules a `forbid_cycle` rule covers.
- L106 `_in_scope(module: str, prefix: str)` (function)
- L110 `_cycles(graph: dict[str, set[str]])` (function) — One representative cycle per strongly connected component, in a stable
- L161 `_scope_regex(scope: str)` (function) — Translate a scope glob to a regex with path-aware semantics.
- L201 `rule_applies(relpath: str, rule)` (function) — Is this file inside the rule's scope and outside its exception?
- L208 `scope_matches(relpath: str, scope: str)` (function) — Does `relpath` fall inside `scope`?
- L223 `load_rules(store: Store)` (function)
- L227 `_forbid_import(relpath: str, text: str, rule: Rule)` (function)
- L262 `_forbid_import_specifiers(relpath: str, text: str, rule: Rule)` (function) — Non-Python: match the rule's target as a prefix of the import specifier
- L278 `_imported_modules(tree: ast.Module, relpath: str)` (function) — All imported module strings (absolute dotted form, relative imports
- L296 `_require_import(relpath: str, text: str, rule: Rule)` (function) — Mandatory-seam check: emit ONE file-level violation when a required import
- L310 `_forbid_layer_import(relpath: str, text: str, rule: Rule)` (function) — Layering check: forbid importing any module whose dotted path matches the
- L340 `_forbid_pattern(relpath: str, text: str, rule: Rule)` (function)
- L352 `_violation(rule: Rule, relpath: str, line: int, default_msg: str)` (function)
- L364 `strict_failures(violations, threshold: str | None=None)` (function) — Violations that should fail --strict: all of them when threshold is None
- L381 `violations_for_file(relpath: str, text: str, rule: Rule)` (function)
- L388 `check_drift(store: Store, files)` (function)
