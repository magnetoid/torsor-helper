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

# src/torsor_helper/languages/python.py

Symbols in `src/torsor_helper/languages/python.py`.

- L11 `parse_quietly(source: str)` (function) — `ast.parse` for someone else's code: None instead of an exception, and
- L27 `_signature(fn: ast.FunctionDef | ast.AsyncFunctionDef)` (function)
- L34 `_first_line(text: str | None)` (function)
- L38 `extract_symbols(source: str, module: str)` (function)
- L64 `absolute_from_module(node: ast.ImportFrom, module: str)` (function) — Resolve an ImportFrom's base module to absolute dotted form, using the
- L84 `_import_aliases(tree: ast.Module, module: str)` (function) — Map each imported name to the module it resolves to (best-effort).
- L119 `_owners(tree: ast.Module)` (function) — Yield (owner_symbol, root_node) pairs covering the whole module body, so
- L140 `extract_edges(source: str, module: str)` (function) — Extract resolved reference edges from a module via AST (no substring
- L197 `extract(source: str, module: str)` (function)
- L206 `complexity(text: str, module: str='')` (function)
