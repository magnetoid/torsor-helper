---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T05:04:01'
updated: '2026-09-04T05:04:01'
---

# src/torsor_helper/cartographer.py

Symbols in `src/torsor_helper/cartographer.py`.

- L17 `_signature(fn: ast.FunctionDef | ast.AsyncFunctionDef)` (function)
- L24 `_first_line(text: str | None)` (function)
- L28 `extract_symbols(source: str, module: str)` (function)
- L55 `norm_module(module: str)` (function) — Normalize a module key to dotted form so a file relpath ("pkg/dates.py")
- L77 `absolute_from_module(node: ast.ImportFrom, module: str)` (function) — Resolve an ImportFrom's base module to absolute dotted form, using the
- L97 `_import_aliases(tree: ast.Module, module: str)` (function) — Map each imported name to the module it resolves to (best-effort).
- L122 `_owners(tree: ast.Module)` (function) — Yield (owner_symbol, root_node) pairs covering the whole module body, so
- L143 `extract_edges(source: str, module: str)` (function) — Extract resolved reference edges from a module via AST (no substring
- L201 `iter_source_files(root: Path, ignore: set[str]=DEFAULT_IGNORE)` (function)
- L212 `repo_fingerprint(root: Path, ignore: set[str]=DEFAULT_IGNORE)` (function) — A cheap O(stat) digest of the repo's *.py files (relpath, mtime, size).
- L229 `_scan(root: Path, paths: list[str] | None, ignore: set[str])` (function)
- L257 `compute_refs(symbols: list[Symbol], edges: list[SymbolEdge])` (function) — Set each symbol's `refs` in place from the given edge set. refs = count of
- L274 `scanned_modules(root: Path, paths: list[str])` (function) — The module keys a partial scan of `paths` covers — mirrors how `_scan`
- L289 `scan_repo(root: Path, paths: list[str] | None=None, ignore: set[str]=DEFAULT_IGNORE)` (function)
- L293 `scan_repo_with_edges(root: Path, paths: list[str] | None=None, ignore: set[str]=DEFAULT_IGNORE)` (function)
- L299 `render_map(symbols: list[Symbol], *, overview_tokens: int=2000, chars_per_token: int=4)` (function)
