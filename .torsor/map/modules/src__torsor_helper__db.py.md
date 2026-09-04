---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T05:04:02'
updated: '2026-09-04T05:04:02'
---

# src/torsor_helper/db.py

Symbols in `src/torsor_helper/db.py`.

- L15 `connect(path: Path)` (function)
- L29 `_create_schema(conn: sqlite3.Connection)` (function)
- L74 `meta_get(conn, key)` (function)
- L79 `meta_set(conn, key, value)` (function)
- L86 `pack(vec: Sequence[float])` (function)
- L90 `unpack(blob: bytes)` (function)
- L94 `note_hashes(conn)` (function)
- L98 `note_stats(conn)` (function) — {path: {content_hash, mtime_ns, size}} — the indexer's skip-screen inputs.
- L106 `note_count(conn)` (function)
- L110 `update_note_stat(conn, path, mtime_ns, size)` (function)
- L114 `upsert_note(conn, path, content_hash, tier, type_, kind, title, updated, status='active', mtime_ns=None, size=None)` (function)
- L127 `note_row(conn, path)` (function)
- L132 `replace_fts(conn, path, title, body)` (function)
- L137 `body_of(conn, path)` (function)
- L142 `_note_paths(conn)` (function)
- L146 `_resolve_slug(paths: list[str], slug: str)` (function) — First (sorted) note whose path ends in `<slug>.md` — literal matching, so
- L156 `replace_edges(conn, src, slugs)` (function)
- L166 `reresolve_edges(conn)` (function) — Second resolution pass over ALL edges: insert-time resolution only sees
- L180 `neighbors(conn, path)` (function)
- L189 `upsert_vector(conn, path, vec)` (function)
- L198 `delete_note(conn, path)` (function)
- L205 `get_vectors(conn, paths)` (function) — Return {path: np.ndarray} for the given paths that have a stored vector.
- L215 `cosine_search(conn, qvec, limit)` (function)
- L237 `fts_search(conn, query, limit)` (function)
- L249 `bump_access(conn, paths)` (function)
- L254 `replace_all_symbols(conn, symbols)` (function)
- L263 `replace_all_edges(conn, edges)` (function)
- L272 `who_references(conn, resolved_module, name)` (function) — Return [(caller, module)] of references to `name` resolving to `resolved_module`.
- L282 `call_graph_edges(conn)` (function) — Distinct (caller, referenced_name, resolved_module) directed edges of the
- L293 `symbol_fan_in(conn)` (function) — In-degree of each referenced symbol: (resolved_module, referenced_name,
- L306 `module_edges(conn)` (function) — Distinct (module, resolved_module) pairs for module-level dependency views.
- L315 `search_symbols(conn, query, limit=10)` (function)
- L336 `modules(conn)` (function)
- L340 `all_symbols(conn)` (function) — Lightweight dicts for every mapped symbol — for fuzzy-scoring by the finder.
- L346 `load_symbols(conn)` (function) — Full Symbol objects for every mapped symbol — used when merging a partial
- L357 `load_edges(conn)` (function) — Full SymbolEdge objects for every recorded reference edge.
- L369 `find_clock(conn)` (function)
- L373 `bump_path_access(conn, paths)` (function) — Record that these files were surfaced by a find — frecency signal. The
- L389 `path_access_map(conn)` (function)
- L393 `log_op(conn, op, args)` (function) — Record one deterministic-tool call — the frequency signal behind 'recipes'
- L406 `top_ops(conn, limit=10)` (function)
- L414 `op_totals(conn)` (function) — Total hits per op, aggregated across args — the per-session delta baseline
- L421 `save_complexity_snapshot(conn, mapping)` (function) — Replace the stored per-file complexity baseline (for trend detection).
- L431 `load_complexity_snapshot(conn)` (function)
- L435 `top_accessed(conn, limit=5)` (function)
