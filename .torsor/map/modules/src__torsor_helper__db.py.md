---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/db.py

Symbols in `src/torsor_helper/db.py`.

- L15 `connect(path: Path)` (function)
- L29 `_create_schema(conn: sqlite3.Connection)` (function)
- L80 `meta_get(conn, key)` (function)
- L85 `meta_set(conn, key, value)` (function)
- L92 `pack(vec: Sequence[float])` (function)
- L96 `unpack(blob: bytes)` (function)
- L100 `note_hashes(conn)` (function)
- L104 `note_stats(conn)` (function) — {path: {content_hash, mtime_ns, size}} — the indexer's skip-screen inputs.
- L112 `note_count(conn)` (function)
- L116 `update_note_stat(conn, path, mtime_ns, size)` (function)
- L120 `upsert_note(conn, path, content_hash, tier, type_, kind, title, updated, status='active', mtime_ns=None, size=None)` (function)
- L133 `note_row(conn, path)` (function)
- L138 `replace_fts(conn, path, title, body)` (function)
- L143 `body_of(conn, path)` (function)
- L148 `_note_paths(conn)` (function)
- L152 `_resolve_slug(paths: list[str], slug: str)` (function) — First (sorted) note whose path ends in `<slug>.md` — literal matching, so
- L162 `replace_edges(conn, src, slugs)` (function)
- L172 `reresolve_edges(conn)` (function) — Second resolution pass over ALL edges: insert-time resolution only sees
- L186 `neighbors(conn, path)` (function)
- L195 `upsert_vector(conn, path, vec)` (function)
- L204 `delete_note(conn, path)` (function)
- L211 `get_vectors(conn, paths)` (function) — Return {path: np.ndarray} for the given paths that have a stored vector.
- L221 `cosine_search(conn, qvec, limit)` (function)
- L243 `fts_search(conn, query, limit)` (function)
- L255 `bump_access(conn, paths)` (function)
- L260 `replace_all_symbols(conn, symbols)` (function)
- L269 `replace_all_edges(conn, edges)` (function)
- L279 `who_references(conn, resolved_module, name)` (function) — Return [(caller, module)] of references to `name` resolving to `resolved_module`.
- L289 `call_graph_edges(conn)` (function) — Distinct (caller, referenced_name, resolved_module) directed edges of the
- L300 `symbol_fan_in(conn)` (function) — In-degree of each referenced symbol: (resolved_module, referenced_name,
- L313 `module_edges(conn)` (function) — Distinct (module, resolved_module) pairs for module-level dependency views.
- L322 `search_symbols(conn, query, limit=10)` (function)
- L343 `modules(conn)` (function)
- L347 `all_symbols(conn)` (function) — Lightweight dicts for every mapped symbol — for fuzzy-scoring by the finder.
- L353 `load_symbols(conn)` (function) — Full Symbol objects for every mapped symbol — used when merging a partial
- L364 `load_edges(conn)` (function) — Full SymbolEdge objects for every recorded reference edge.
- L376 `find_clock(conn)` (function)
- L380 `bump_path_access(conn, paths)` (function) — Record that these files were surfaced by a find — frecency signal. The
- L396 `path_access_map(conn)` (function)
- L400 `log_op(conn, op, args)` (function) — Record one deterministic-tool call — the frequency signal behind 'recipes'
- L413 `top_ops(conn, limit=10)` (function)
- L421 `op_totals(conn)` (function) — Total hits per op, aggregated across args — the per-session delta baseline
- L428 `save_complexity_snapshot(conn, mapping)` (function) — Replace the stored per-file complexity baseline (for trend detection).
- L438 `load_complexity_snapshot(conn)` (function)
- L442 `top_accessed(conn, limit=5)` (function)
