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

# src/torsor_helper/cartographer.py

Symbols in `src/torsor_helper/cartographer.py`.

- L26 `iter_files(root: Path, ignore: set[str]=DEFAULT_IGNORE, *, skip_hidden: bool=False)` (function) — Every file under `root` not inside an ignored directory, sorted by path.
- L51 `iter_source_files(root: Path, ignore: set[str]=DEFAULT_IGNORE)` (function)
- L63 `repo_fingerprint(root: Path, ignore: set[str]=DEFAULT_IGNORE)` (function) — A cheap O(stat) digest of the repo's source files (relpath, mtime, size).
- L80 `_scan(root: Path, paths: list[str] | None, ignore: set[str])` (function)
- L114 `compute_refs(symbols: list[Symbol], edges: list[SymbolEdge])` (function) — Set each symbol's `refs` in place from the given edge set. refs = count of
- L136 `persistable_edges(edges: list[SymbolEdge])` (function) — The edges worth writing to the index: resolved ones, plus every edge of a
- L166 `scanned_modules(root: Path, paths: list[str])` (function) — The module keys a partial scan of `paths` covers — mirrors how `_scan`
- L181 `scan_repo(root: Path, paths: list[str] | None=None, ignore: set[str]=DEFAULT_IGNORE)` (function)
- L185 `scan_repo_with_edges(root: Path, paths: list[str] | None=None, ignore: set[str]=DEFAULT_IGNORE)` (function)
- L191 `render_map(symbols: list[Symbol], *, overview_tokens: int=2000, chars_per_token: int=4)` (function)
