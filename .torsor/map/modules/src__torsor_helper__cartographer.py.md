---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/cartographer.py

Symbols in `src/torsor_helper/cartographer.py`.

- L24 `iter_files(root: Path, ignore: set[str]=DEFAULT_IGNORE, *, skip_hidden: bool=False)` (function) — Every file under `root` not inside an ignored directory, sorted by path.
- L49 `iter_source_files(root: Path, ignore: set[str]=DEFAULT_IGNORE)` (function)
- L54 `repo_fingerprint(root: Path, ignore: set[str]=DEFAULT_IGNORE)` (function) — A cheap O(stat) digest of the repo's source files (relpath, mtime, size).
- L71 `_scan(root: Path, paths: list[str] | None, ignore: set[str])` (function)
- L105 `compute_refs(symbols: list[Symbol], edges: list[SymbolEdge])` (function) — Set each symbol's `refs` in place from the given edge set. refs = count of
- L127 `scanned_modules(root: Path, paths: list[str])` (function) — The module keys a partial scan of `paths` covers — mirrors how `_scan`
- L142 `scan_repo(root: Path, paths: list[str] | None=None, ignore: set[str]=DEFAULT_IGNORE)` (function)
- L146 `scan_repo_with_edges(root: Path, paths: list[str] | None=None, ignore: set[str]=DEFAULT_IGNORE)` (function)
- L152 `render_map(symbols: list[Symbol], *, overview_tokens: int=2000, chars_per_token: int=4)` (function)
