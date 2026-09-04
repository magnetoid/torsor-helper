---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T15:38:11'
updated: '2026-09-04T15:38:11'
---

# src/torsor_helper/languages/python.py

Symbols in `src/torsor_helper/languages/python.py`.

- L9 `_signature(fn: ast.FunctionDef | ast.AsyncFunctionDef)` (function)
- L16 `_first_line(text: str | None)` (function)
- L20 `extract_symbols(source: str, module: str)` (function)
- L47 `absolute_from_module(node: ast.ImportFrom, module: str)` (function) — Resolve an ImportFrom's base module to absolute dotted form, using the
- L67 `_import_aliases(tree: ast.Module, module: str)` (function) — Map each imported name to the module it resolves to (best-effort).
- L92 `_owners(tree: ast.Module)` (function) — Yield (owner_symbol, root_node) pairs covering the whole module body, so
- L113 `extract_edges(source: str, module: str)` (function) — Extract resolved reference edges from a module via AST (no substring
- L171 `extract(source: str, module: str)` (function)
- L180 `complexity(text: str, module: str='')` (function)
