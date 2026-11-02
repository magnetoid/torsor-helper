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

# src/torsor_helper/operations/graph.py

Symbols in `src/torsor_helper/operations/graph.py`.

- L24 `map_repo(store: Store, config: TorsorConfig, paths: list[str] | None=None, force: bool=False)` (function)
- L127 `_map_note_unchanged(store, target, body: str)` (function) — True when `target` already holds exactly this rendered body.
- L137 `_language_counts(modules, root=None)` (function) — Mapped module count per available language, plus — under "unavailable" —
- L150 `_unavailable_language_counts(root)` (function)
- L162 `impact(store: Store, config: TorsorConfig, symbol: str, *, limit: int | None=None)` (function) — Blast radius of a symbol: who references it, across files, via the
- L208 `_mentions(conn, store: Store, symbol: str, base: str)` (function) — Notes naming this symbol, as {path, title, type}. Both the dotted spelling
- L227 `connect(store: Store, config: TorsorConfig, source: str, target: str, *, max_hops: int | None=None)` (function) — Shortest directed path through the symbol call graph from `source` to
