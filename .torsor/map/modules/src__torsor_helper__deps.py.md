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

# src/torsor_helper/deps.py

Symbols in `src/torsor_helper/deps.py`.

- L35 `stdlib_names()` (function)
- L39 `_norm(name: str)` (function)
- L43 `_site_packages_top_levels(site: Path)` (function)
- L79 `installed_import_names(root: Path)` (function) — Top-level import names actually installed in the project's own virtualenv
- L95 `first_party_names(root: Path)` (function) — Top-level packages/modules defined in the repo (root and src/ layouts).
- L112 `_dist_from_spec(spec: str)` (function)
- L117 `declared_import_names(root: Path)` (function) — Best-effort import names from declared dependencies (pyproject + requirements),
- L156 `_dist_import_candidates(name: str)` (function) — Import names a distribution *might* provide, without installing it.
- L184 `_declared_in(directory: Path)` (function) — Import names declared by one directory's pyproject.toml and
- L194 `_catches_import_error(node)` (function)
- L206 `_import_statements(stmts, guarded: bool=False)` (function) — Yield (import node, guarded) for every import statement, in one pass.
- L252 `_import_candidates(text: str)` (function) — Top-level names every import in `text` could refer to, or None when the
- L270 `_top_imports(text: str)` (function)
- L290 `_js_package(spec: str)` (function) — Bare specifier → package name ('lodash/fp' → 'lodash', '@s/p/x' → '@s/p');
- L311 `_read_manifest(path: Path)` (function) — A package.json or tsconfig, parsed; {} when it cannot be. Never raises.
- L320 `_loads_jsonc(text: str)` (function) — json.loads for JSON-with-comments, which is what tsconfig actually is.
- L360 `_skip_blank(text: str, k: int)` (function) — Index of the next character that is neither whitespace nor inside a
- L379 `_ManifestIndex` (class) — Every manifest in the repo, read once per `unknown_imports` call.
- L384 `__init__(self, root: Path)` (method)
- L398 `js_known(self, relpath: str)` (method) — Package names a file at `relpath` can import: builtins, every
- L419 `_installed(self, d: str)` (method)
- L424 `is_alias(self, spec: str)` (method)
- L442 `py_known(self, relpath: str)` (method) — What a Python file can import beyond stdlib/venv/root: the modules
- L462 `go_known(self, relpath: str)` (method)
- L471 `_types_target(name: str)` (function)
- L476 `_ancestors(parent: str)` (function) — "" and every directory prefix of `parent`, shallowest first.
- L482 `_node_modules_names(nm: Path)` (function)
- L500 `_manifest_index(root: Path)` (function) — One walk over the repo for every package.json, tsconfig*.json and go.mod.
- L550 `_collect_aliases(index: _ManifestIndex, config_dir: Path, data: dict)` (function)
- L575 `_unknown_js_imports(root: Path, relpath: str, text: str, index: _ManifestIndex)` (function)
- L592 `_go_mod_prefixes(mod: Path)` (function)
- L605 `_go_module_path(mod: Path)` (function)
- L613 `_unknown_go_imports(root: Path, relpath: str, text: str, index: _ManifestIndex)` (function)
- L627 `unknown_imports(root: Path, files)` (function) — Flag top-level absolute imports that resolve to NO known package — a
