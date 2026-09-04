---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T05:04:02'
updated: '2026-09-04T05:04:02'
---

# src/torsor_helper/deps.py

Symbols in `src/torsor_helper/deps.py`.

- L24 `stdlib_names()` (function)
- L28 `_norm(name: str)` (function)
- L32 `_site_packages_top_levels(site: Path)` (function)
- L68 `installed_import_names(root: Path)` (function) — Top-level import names actually installed in the project's own virtualenv
- L84 `first_party_names(root: Path)` (function) — Top-level packages/modules defined in the repo (root and src/ layouts).
- L101 `_dist_from_spec(spec: str)` (function)
- L106 `declared_import_names(root: Path)` (function) — Best-effort import names from declared dependencies (pyproject + requirements),
- L150 `_top_imports(text: str)` (function)
- L168 `unknown_imports(root: Path, files)` (function) — Flag top-level absolute imports that resolve to NO known package — a
