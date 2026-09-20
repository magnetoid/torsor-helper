---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T01:02:54'
updated: '2026-09-21T01:02:54'
rules: []
---

# src/torsor_helper/operations/graph.py

Symbols in `src/torsor_helper/operations/graph.py`.

- L22 `map_repo(store: Store, config: TorsorConfig, paths: list[str] | None=None, force: bool=False)` (function)
- L103 `_map_note_unchanged(store, target, body: str)` (function) — True when `target` already holds exactly this rendered body.
- L113 `_language_counts(modules, root=None)` (function) — Mapped module count per available language, plus — under "unavailable" —
- L126 `_unavailable_language_counts(root)` (function)
- L138 `export_project(store: Store, config: TorsorConfig)` (function)
- L141 `find_targets(store: Store, config: TorsorConfig, query: str, *, mode: str='fuzzy', limit: int=20, include_files: bool=True, include_symbols: bool=True)` (function) — Fuzzy/literal/regex find over repo files + mapped symbols, frecency-ranked.
- L148 `impact(store: Store, config: TorsorConfig, symbol: str, *, limit: int | None=None)` (function) — Blast radius of a symbol: who references it, across files, via the
- L185 `connect(store: Store, config: TorsorConfig, source: str, target: str, *, max_hops: int | None=None)` (function) — Shortest directed path through the symbol call graph from `source` to
