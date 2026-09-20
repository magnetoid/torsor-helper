---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/deps.py

Symbols in `src/torsor_helper/deps.py`.

- L35 `stdlib_names()` (function)
- L39 `_norm(name: str)` (function)
- L43 `_site_packages_top_levels(site: Path)` (function)
- L79 `installed_import_names(root: Path)` (function) — Top-level import names actually installed in the project's own virtualenv
- L95 `first_party_names(root: Path)` (function) — Top-level packages/modules defined in the repo (root and src/ layouts).
- L112 `_dist_from_spec(spec: str)` (function)
- L117 `declared_import_names(root: Path)` (function) — Best-effort import names from declared dependencies (pyproject + requirements),
- L161 `_top_imports(text: str)` (function)
- L179 `_js_package(spec: str)` (function) — Bare specifier → package name ('lodash/fp' → 'lodash', '@s/p/x' → '@s/p');
- L189 `_js_known(root: Path)` (function)
- L215 `_unknown_js_imports(root: Path, relpath: str, text: str, known: set[str])` (function)
- L231 `_go_known_prefixes(root: Path)` (function)
- L247 `_unknown_go_imports(root: Path, relpath: str, text: str, prefixes: list[str])` (function)
- L260 `unknown_imports(root: Path, files)` (function) — Flag top-level absolute imports that resolve to NO known package — a
