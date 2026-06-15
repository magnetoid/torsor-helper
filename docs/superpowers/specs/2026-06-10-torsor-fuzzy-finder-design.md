# torsor-helper — Fuzzy + Frecency Finder (design)

**Goal:** Give agents a fast **"find"** capability — fuzzy, typo-tolerant matching over the repo's **files** and torsor's **mapped symbols**, ranked by match quality + **frecency** (recent + frequently-found). Inspired by [dmtrKovalenko/fff](https://github.com/dmtrKovalenko/fff), adopting its *ideas* (fuzzy + frecency) in pure Python while respecting torsor's invariants.

**Explicitly NOT replicated (out of scope, by design):** fff's Rust/SIMD speed, a resident daemon + file watcher, and language bindings. torsor stays a **per-call, stateless, deterministic, offline** MCP tool. For fff-grade speed on huge monorepos, run fff alongside torsor — they're complementary. No "fastest" claims.

## Invariants
- No new required dependency (stdlib + git subprocess only). Local-first, offline.
- Deterministic: ranking is a pure function of (query, file list, symbol table, and the recorded find-access sequence) — **no wall-clock**. Frecency recency uses a monotonic per-find counter, not time.
- The frecency table lives in the rebuildable `.index/` DB (a soft signal; losing it on rebuild is fine).

## Design

### `finder.py`
- `list_files(root)` — `git ls-files --cached --others --exclude-standard` (tracked + untracked-not-ignored, respects `.gitignore`); falls back to an `os.walk` filtered by `cartographer.DEFAULT_IGNORE` outside git. Always drops `DEFAULT_IGNORE` dirs (incl. `.torsor`). Returns sorted relative posix paths.
- `fuzzy_score(query, text)` — greedy **subsequence** scorer with bonuses for consecutive runs, word/path **boundary** matches (after `/ _ - .` or camelCase humps), and smart-case (case-insensitive unless the query has uppercase). Scores the **basename** separately and prefers it (file finders favor filename matches). Returns a float or `None` (no match). Plus `literal` (substring) and `regex` modes.
- `find(store, config, query, *, mode, limit, include_files, include_symbols)` — score every file + every symbol name, multiply files by a **frecency boost** and symbols by a small `refs` boost, sort, take top-`limit`, then **bump frecency** for the returned files. Returns `[{type: file|symbol, path|name, module?, line?, score}]`.

### `db.py` (SCHEMA_VERSION → 5, additive)
- `path_access(path PRIMARY KEY, count INTEGER, last_seen INTEGER)` + a `meta.find_clock`.
- `bump_path_access(conn, paths)` (increment count, stamp `last_seen = ++find_clock`), `path_access_map(conn)`, `find_clock(conn)`, `all_symbols(conn)`.
- frecency boost `= 1 + 0.5·log1p(count) + 0.5·(last_seen/clock)`; unseen files → boost 1.0 (no cold-start penalty).

### Surfaces
- `operations.find_targets(store, config, query, *, mode, limit, include_files, include_symbols)`.
- CLI `torsor find <query> [--mode fuzzy|literal|regex] [--limit N] [--files-only] [--symbols-only]`.
- MCP tool `find_files(query, mode="fuzzy", limit=20)`.

## Tests (offline, deterministic)
- `fuzzy_score`: subsequence matches; non-subsequence → None; basename preference (`deps` ranks `deps.py` over `test_deps.py`); consecutive/boundary bonuses; smart-case.
- `list_files`: respects ignores, includes tracked + untracked, excludes `.torsor`.
- `find`: end-to-end over a mapped repo returns the expected file + symbol; `--files-only`/`--symbols-only`; `path_access` populated after a find; frecency boosts a previously-found file.
- `db`: `bump_path_access`/`path_access_map` roundtrip; SCHEMA_VERSION == 5.

## Build order
db (table + helpers) → finder (scorer → list_files → find) → operations → CLI + MCP → docs (README feature row + CHANGELOG) → review → merge.
