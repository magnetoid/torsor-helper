---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T01:13:27'
updated: '2026-09-21T01:13:27'
rules: []
---

# src/torsor_helper/db.py

Symbols in `src/torsor_helper/db.py`.

- L15 `connect(path: Path)` (function)
- L34 `_schema_is_current(conn: sqlite3.Connection)` (function) — True when this DB was already built by this version.
- L57 `_create_schema(conn: sqlite3.Connection)` (function)
- L126 `meta_get(conn, key)` (function)
- L131 `meta_set(conn, key, value)` (function)
- L138 `pack(vec: Sequence[float])` (function) — Store L2-normalized, so cosine similarity at query time is a plain dot
- L149 `unpack(blob: bytes)` (function)
- L153 `note_hashes(conn)` (function)
- L157 `note_stats(conn)` (function) — {path: {content_hash, mtime_ns, size}} — the indexer's skip-screen inputs.
- L165 `note_count(conn)` (function)
- L169 `update_note_stat(conn, path, mtime_ns, size)` (function)
- L173 `upsert_note(conn, path, content_hash, tier, type_, kind, title, updated, status='active', mtime_ns=None, size=None)` (function)
- L186 `note_row(conn, path)` (function)
- L191 `note_rows(conn, paths)` (function) — {path: row} for many paths in one statement. The per-path note_row was an
- L205 `_fts_rowid(conn, path)` (function)
- L210 `replace_fts(conn, path, title, body)` (function)
- L222 `body_of(conn, path)` (function)
- L230 `_note_paths(conn)` (function)
- L234 `SlugIndex` (class) — slug -> the first (sorted) note path ending in `<slug>.md`.
- L245 `__init__(self, conn)` (method)
- L262 `is_ambiguous(self, slug: str)` (method) — True when more than one note shares this basename. A slug containing
- L267 `resolve(self, slug: str)` (method)
- L278 `_resolve_slug(paths: list[str], slug: str)` (function) — Literal suffix match, so LIKE wildcards in a slug can't match the wrong
- L288 `replace_edges(conn, src, slugs, index: SlugIndex | None=None)` (function) — `index` lets a bulk caller build the slug lookup once instead of running a
- L300 `reresolve_edges(conn)` (function) — Second resolution pass over ALL edges: insert-time resolution only sees
- L314 `neighbors(conn, path)` (function)
- L323 `upsert_vector(conn, path, vec)` (function)
- L332 `delete_note(conn, path)` (function)
- L342 `get_vectors(conn, paths)` (function) — Return {path: np.ndarray} for the given paths that have a stored vector.
- L356 `vectors_match(conn, embedder_identity: str)` (function) — True when the stored vectors were built by this run's embedder. A False
- L364 `cosine_search(conn, qvec, limit)` (function) — Top-`limit` paths by cosine similarity to `qvec`.
- L390 `fts_search(conn, query, limit)` (function)
- L402 `bump_access(conn, paths)` (function)
- L407 `replace_all_symbols(conn, symbols)` (function)
- L416 `replace_all_edges(conn, edges)` (function)
- L426 `who_references(conn, resolved_module, name)` (function) — Return [(caller, module)] of references to `name` resolving to `resolved_module`.
- L436 `call_graph_edges(conn)` (function) — Distinct (caller, referenced_name, resolved_module) directed edges of the
- L447 `symbol_fan_in(conn)` (function) — In-degree of each referenced symbol: (resolved_module, referenced_name,
- L460 `module_edges(conn)` (function) — Distinct (module, resolved_module) pairs for module-level dependency views.
- L469 `search_symbols(conn, query, limit=10)` (function)
- L490 `modules(conn)` (function)
- L494 `all_symbols(conn)` (function) — Lightweight dicts for every mapped symbol — for fuzzy-scoring by the finder.
- L500 `load_symbols(conn)` (function) — Full Symbol objects for every mapped symbol — used when merging a partial
- L511 `load_edges(conn)` (function) — Full SymbolEdge objects for every recorded reference edge.
- L523 `find_clock(conn)` (function)
- L527 `bump_path_access(conn, paths)` (function) — Record that these files were surfaced by a find — frecency signal. The
- L543 `path_access_map(conn)` (function)
- L547 `log_op(conn, op, args)` (function) — Record one deterministic-tool call — the frequency signal behind 'recipes'
- L560 `top_ops(conn, limit=10)` (function)
- L568 `op_totals(conn)` (function) — Total hits per op, aggregated across args — the per-session delta baseline
- L575 `save_complexity_snapshot(conn, mapping)` (function) — Replace the stored per-file complexity baseline (for trend detection).
- L585 `load_complexity_snapshot(conn)` (function)
- L589 `top_accessed(conn, limit=5)` (function)
