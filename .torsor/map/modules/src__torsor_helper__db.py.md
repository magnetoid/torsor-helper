---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T17:33:16'
updated: '2026-09-21T17:33:16'
rules: []
---

# src/torsor_helper/db.py

Symbols in `src/torsor_helper/db.py`.

- L15 `connect(path: Path)` (function)
- L34 `_schema_is_current(conn: sqlite3.Connection)` (function) — True when this DB was already built by this version.
- L57 `_create_schema(conn: sqlite3.Connection)` (function)
- L133 `meta_get(conn, key)` (function)
- L138 `meta_set(conn, key, value)` (function)
- L145 `pack(vec: Sequence[float])` (function) — Store L2-normalized, so cosine similarity at query time is a plain dot
- L156 `unpack(blob: bytes)` (function)
- L160 `note_hashes(conn)` (function)
- L164 `note_stats(conn)` (function) — {path: {content_hash, mtime_ns, size}} — the indexer's skip-screen inputs.
- L172 `note_count(conn)` (function)
- L176 `update_note_stat(conn, path, mtime_ns, size)` (function)
- L180 `upsert_note(conn, path, content_hash, tier, type_, kind, title, updated, status='active', mtime_ns=None, size=None)` (function)
- L193 `note_row(conn, path)` (function)
- L198 `note_rows(conn, paths)` (function) — {path: row} for many paths in one statement. The per-path note_row was an
- L212 `_fts_rowid(conn, path)` (function)
- L217 `replace_fts(conn, path, title, body)` (function)
- L229 `body_of(conn, path)` (function)
- L237 `_note_paths(conn)` (function)
- L241 `SlugIndex` (class) — slug -> the first (sorted) note path ending in `<slug>.md`.
- L252 `__init__(self, conn)` (method)
- L271 `is_ambiguous(self, slug: str)` (method) — True when more than one note shares this basename. A slug containing
- L276 `resolve(self, slug: str)` (method)
- L288 `_resolve_slug(paths: list[str], slug: str)` (function) — Literal suffix match, so LIKE wildcards in a slug can't match the wrong
- L298 `replace_edges(conn, src, slugs, index: SlugIndex | None=None)` (function) — `index` lets a bulk caller build the slug lookup once instead of running a
- L310 `replace_note_symbols(conn, path, symbols)` (function)
- L318 `notes_mentioning(conn, symbol: str)` (function) — Note paths that name `symbol` in backticks, newest first.
- L333 `reresolve_edges(conn)` (function) — Second resolution pass over ALL edges: insert-time resolution only sees
- L347 `neighbors(conn, path)` (function)
- L356 `upsert_vector(conn, path, vec)` (function)
- L365 `delete_note(conn, path)` (function)
- L376 `get_vectors(conn, paths)` (function) — Return {path: np.ndarray} for the given paths that have a stored vector.
- L390 `vectors_match(conn, embedder_identity: str)` (function) — True when the stored vectors were built by this run's embedder. A False
- L398 `cosine_search(conn, qvec, limit)` (function) — Top-`limit` paths by cosine similarity to `qvec`.
- L424 `fts_search(conn, query, limit)` (function)
- L436 `bump_access(conn, paths)` (function)
- L441 `replace_all_symbols(conn, symbols)` (function)
- L450 `replace_all_edges(conn, edges)` (function)
- L460 `who_references(conn, resolved_module, name)` (function) — Return [(caller, module)] of references to `name` resolving to `resolved_module`.
- L470 `call_graph_edges(conn)` (function) — Distinct (caller, referenced_name, resolved_module) directed edges of the
- L481 `symbol_fan_in(conn)` (function) — In-degree of each referenced symbol: (resolved_module, referenced_name,
- L494 `module_edges(conn)` (function) — Distinct (module, resolved_module) pairs for module-level dependency views.
- L503 `search_symbols(conn, query, limit=10)` (function)
- L524 `modules(conn)` (function)
- L528 `all_symbols(conn)` (function) — Lightweight dicts for every mapped symbol — for fuzzy-scoring by the finder.
- L534 `load_symbols(conn)` (function) — Full Symbol objects for every mapped symbol — used when merging a partial
- L545 `load_edges(conn)` (function) — Full SymbolEdge objects for every recorded reference edge.
- L557 `find_clock(conn)` (function)
- L561 `bump_path_access(conn, paths)` (function) — Record that these files were surfaced by a find — frecency signal. The
- L577 `path_access_map(conn)` (function)
- L581 `log_op(conn, op, args)` (function) — Record one deterministic-tool call — the frequency signal behind 'recipes'
- L594 `top_ops(conn, limit=10)` (function)
- L602 `op_totals(conn)` (function) — Total hits per op, aggregated across args — the per-session delta baseline
- L609 `save_complexity_snapshot(conn, mapping)` (function) — Replace the stored per-file complexity baseline (for trend detection).
- L619 `load_complexity_snapshot(conn)` (function)
- L623 `top_accessed(conn, limit=5)` (function)
