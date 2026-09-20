---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T00:06:46'
updated: '2026-09-21T00:06:46'
---

# src/torsor_helper/operations/graph.py

Symbols in `src/torsor_helper/operations/graph.py`.

- L22 `map_repo(store: Store, config: TorsorConfig, paths: list[str] | None=None, force: bool=False)` (function)
- L93 `_map_note_unchanged(store, target, body: str)` (function) — True when `target` already holds exactly this rendered body.
- L103 `_language_counts(modules, root=None)` (function) — Mapped module count per available language, plus — under "unavailable" —
- L116 `_unavailable_language_counts(root)` (function)
- L128 `export_project(store: Store, config: TorsorConfig)` (function)
- L131 `find_targets(store: Store, config: TorsorConfig, query: str, *, mode: str='fuzzy', limit: int=20, include_files: bool=True, include_symbols: bool=True)` (function) — Fuzzy/literal/regex find over repo files + mapped symbols, frecency-ranked.
- L138 `impact(store: Store, config: TorsorConfig, symbol: str, *, limit: int | None=None)` (function) — Blast radius of a symbol: who references it, across files, via the
- L175 `connect(store: Store, config: TorsorConfig, source: str, target: str, *, max_hops: int | None=None)` (function) — Shortest directed path through the symbol call graph from `source` to
