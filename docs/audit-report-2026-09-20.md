> **Status (2026-09-20):** approved improvement roadmap. Supersedes the open items of `audit-report-2026-07-18.md`. Recommended phase order: 5 → 0 → 1 → 2 → 3 → 4 → 6 → 7.

# torsor-helper — improvement audit & phased plan (2026-09-20)

## Context

torsor-helper is at v0.6.0 (+ unreleased edit gate). The repo is healthy on every gate we can run:
444 tests pass, ruff clean, `torsor guard --strict` clean, `torsor doctor` OK. But the codebase has
grown ~3× since the last audit (docs/audit-report-2026-07-18.md, v0.4) and several of that audit's
top findings are still open (O(n) vector scan, reindex-on-every-recall, god module, no MCP
integration test). This plan is a fresh, verified inventory plus a phased roadmap that can be
executed alongside feature work. Every finding below was anchored to `file:line` by three
parallel read-only audits and the high-severity ones were re-verified by hand.

Baseline measured today:

| Metric | Value |
|---|---|
| Source | 7,010 lines / 27 modules + `coach/` (9) |
| Tests | 444 functions, 95 files, 5,394 lines |
| Full suite wall time | 21 s unloaded (140 s while three audit agents ran concurrently); slowest test 0.7 s, all git-backed |
| `operations.py` | 1,492 lines, ~70 functions, 29 function-local imports |
| Coach on itself | flags `operations.py`, `cli.py`, `server.py` as hotspots; `cli.py`↔`server.py` 84 % temporal coupling |

Scoring uses the tech-debt formula `Priority = (Impact + Risk) × (6 − Effort)`, each 1–5.

---

## Part 1 — Findings inventory (verified)

### A. Data-loss & security bugs (fix first — all Small)

| # | Finding | Where | I | R | E | Pri |
|---|---|---|---|---|---|---|
| A1 | `hooks install` **replaces the user's whole `.claude/settings.json`** with only torsor's hooks if the file fails `json.loads` (JSONC / trailing comma). Same in `uninstall_hooks`. | operations.py:1414-1428, :1456-1462 | 4 | 5 | 1 | 45 |
| A2 | `merge_settings_hooks` drops an entire hook **group** if *any* hook in it is torsor's → silently deletes foreign hooks that share a group. Docstring claims the opposite. | hooks.py:122-128, :143 | 3 | 4 | 1 | 35 |
| A3 | `run_command` executes `.torsor/commands.md` entries with `shell=True`; reachable from MCP via `record_command` + `verify(run_tests=True)`. Any PR touching `commands.md` = arbitrary shell on the next `verify`. | operations.py:526-535, server.py:137, :206 | 3 | 5 | 2 | 32 |
| A4 | `check_drift(files=[...])` over MCP reads **any absolute/`../` path** (no containment); out-of-root files match `*.py` rules by bare name; `guard --update-baseline` then persists them into committed `baseline.json`. | guard.py:197-208 | 3 | 4 | 1 | 35 |
| A5 | `_set_note_status` (`stale --mark`) and `map_repo` write to `root / rel` with no containment check. | operations.py:1015-1022, :210-212 | 2 | 3 | 1 | 25 |
| A6 | `mcp --http --host 0.0.0.0` warns and **serves anyway**, unauthenticated. | cli.py:91-98 | 3 | 4 | 1 | 35 |
| A7 | `clean --apply --deep` `rmtree`s `.index/` with no confirmation — and that directory holds **non-derivable state** (`coach_state.json` dismissals, `capture_state.json` watermark, `op_log`, `path_access`). | cleaner.py:124-133, coach/report.py:47, operations.py:1103 | 3 | 4 | 2 | 28 |
| A8 | `hooks uninstall --local` targets *only* the local file (help says "also"); `--local` install never removes a prior global install → double SessionStart/handoff firing. | operations.py:1454, :1415, cli.py:727 | 2 | 3 | 1 | 25 |
| A9 | `merge_settings_hooks(data, root=".")` hardcodes root regardless of `--root`; hooks silently no-op when `.torsor/` lives in a subdir. | operations.py:1424, hooks.py:45-49 | 2 | 3 | 1 | 25 |

### B. Correctness (index-as-authority, budgets, parsing)

| # | Finding | Where | I | R | E | Pri |
|---|---|---|---|---|---|---|
| B1 | **Partial `map_repo` rebuilds the rest of the graph from the index**; after `clean --deep` the next post-commit hook writes `.torsor/map/` notes covering only the committed files — and `map/` is git-committed. `cleaner._live_map_notes` likewise deletes committed notes based on `db.modules()`. Violates "never treat the index as authoritative". | operations.py:200-203, cleaner.py:52-68 | 4 | 4 | 3 | 24 |
| B2 | `SCHEMA_VERSION` is write-only: `_create_schema` stamps it unconditionally before anyone reads it; only `indexed_schema` (notes) is checked. A column added to `symbols` breaks old DBs at INSERT time. | db.py:64-71, indexer.py:37 | 3 | 3 | 2 | 24 |
| B3 | `bootstrap_session` appends the Coach "Recommendations" section **after** the budget is spent (no `truncate_to_tokens`) → the 500-token SessionStart digest can overrun on every start/compaction. `list_practices`, `impact`, `get_intent` decisions list, `verify` reasons are also unbudgeted. | operations.py:48-52, :754-769, :567-594, :671-679, :929-959 | 3 | 3 | 1 | 30 |
| B4 | `[[note\|alias]]`, `[[note#section]]`, `[[dir/note]]` are never normalized → edge never resolves **and** `staleness.check_dangling_links` reports a false positive in the one detector designed to be high-precision. | store.py:16, :62-69; db.py:146-153; coach/staleness.py:41-48 | 3 | 3 | 1 | 30 |
| B5 | `_resolve_slug` returns the *first sorted* path ending in `<slug>.md` — duplicate basenames across tiers (`overview.md`, `context.md`) resolve arbitrarily, no ambiguity signal. | db.py:146-153 | 3 | 2 | 2 | 20 |
| B6 | Guard `scope` uses `fnmatch`, where `*` matches `/`: this repo's own ADR 0002 scope `src/torsor_helper/*.py` silently governs `coach/` too, and `src/**/*.ts` (the multi-language spec's prescribed shape) matches **nothing**. Verified today. | guard.py:210 | 3 | 3 | 2 | 24 |
| B7 | `read_note` uses `utf-8` while cartographer/guard/deps use `utf-8-sig` → a BOM'd note loses its frontmatter and tier. | store.py:128 | 2 | 3 | 1 | 25 |
| B8 | `Frontmatter` doesn't declare `kind`/`rules` (survive via `extra="allow"`); a typo'd key is a silent no-op. Non-list `tags:` discards the whole frontmatter. | models.py:39-47, store.py:49-54, indexer.py:67 | 2 | 2 | 1 | 20 |
| B9 | Index stores absolute, OS-native note paths; slug/breadcrumb logic splits on `/` → on Windows every wikilink edge is NULL. Moving the checkout invalidates half the index. | indexer.py:45, db.py:149, indexer.py:22 | 2 | 3 | 2 | 20 |
| B10 | `auto_index=false` only works on a virgin project: once the DB exists, `reindex` runs on every `recall` anyway. | operations.py:109 | 2 | 2 | 1 | 20 |
| B11 | `verify(files=...)` runs staleness project-wide, ignoring `files` → `torsor verify a.py` fails on an unrelated note. | operations.py:946 | 2 | 2 | 1 | 20 |
| B12 | `guard` CLI prints/JSON-emits **all** violations but exits on `new` only; `--json --update-baseline` emits nothing; `--severity` typo → threshold 0; `stale --mark --unmark` silently unmarks. | cli.py:383-403, :385-387, guard.py:172, operations.py:992-995 | 2 | 2 | 1 | 20 |
| B13 | fastembed transient failure (first-run download offline) swaps embedder identity → **full re-embed of the corpus with hashing**, then again when it recovers. Path is `# pragma: no cover`. | embeddings.py:62-78, indexer.py:31-33 | 2 | 3 | 2 | 20 |
| B14 | `export` appends Mermaid into `map/overview.md`; `map_repo` re-renders it from scratch → diagram vanishes on the next commit hook. | export.py:118-119, operations.py:205-212 | 2 | 2 | 2 | 16 |
| B15 | Cartographer reads only `tree.body`: nested classes, inner functions, `if TYPE_CHECKING:` / `try: import` blocks and **function-local imports** are invisible → undercounted `refs`, missing `impact` callers. guard/deps use `ast.walk` (three modules, two import semantics). | cartographer.py:34, :97-119 | 3 | 2 | 3 | 15 |
| B16 | `git ls-files` / `git log --name-only` without `-z` / `core.quotePath=false` → non-ASCII paths come back C-quoted and are unfindable / never hotspots. | finder.py:96-105, coach/hotspots.py:29, coach/coupling.py:18 | 2 | 2 | 1 | 20 |
| B17 | `importance_floors` keyed by uppercase `Tier.name`; a lowercase TOML key silently disables decay. | search.py:109, config.py:14-20 | 1 | 2 | 1 | 15 |

### C. Performance (scaling cliffs)

| # | Finding | Where | I | R | E | Pri |
|---|---|---|---|---|---|---|
| C1 | **Search hot loop**: `note_row` per candidate (N+1), `body_of` (FTS full scan, `path` is UNINDEXED) + `best_snippet` for **every** candidate *before* `limit`; `_mmr_order` O(n²) over all hits; `get_vectors` one SELECT per hit; with `type_`/`kind` the pool becomes the whole corpus. | search.py:69-72, :86, :96-114, :36-59, :122; db.py:132-139, :205-212 | 4 | 3 | 2 | 28 |
| C2 | `cosine_search` fetches every vector blob and loops in Python; `reindex` + `reresolve_edges` (all edges) run on **every** `recall`. | db.py:215-234, indexer.py:93, operations.py:107-118 | 4 | 3 | 2 | 28 |
| C3 | No secondary indexes: `edges(src)`, `symbol_edges(resolved_module, referenced_name)`, `symbols(module)`, `symbols(name)`, `notes(type,kind,status)`. `impact` does one `who_references` full scan **per candidate module**. | db.py:29-61, :272, operations.py:586-590 | 3 | 2 | 1 | 25 |
| C4 | `connect()` runs the full `_create_schema` + `meta_set` + `commit` (a write txn + fsync) on **every** open; `_log_op` opens/commits/closes per op → 3-4 write txns per CLI command. No `PRAGMA synchronous=NORMAL`. | db.py:15-27, operations.py:538-550 | 3 | 2 | 1 | 25 |
| C5 | `replace_edges` calls `_note_paths` (full SELECT) per note → O(N²) full reindex; `replace_fts` DELETE on unindexed column is a full scan per note. | db.py:156-163, :132-134 | 3 | 2 | 2 | 20 |
| C6 | One `recommend()` = 4 git subprocesses, **2 unbounded full-history `git log` walks**, ~3 full-repo AST parses (hotspots, deps, coupling, trend each re-read). | coach/hotspots.py:16-45, coach/coupling.py:14-45, coach/report.py:12-27, coach/trend.py:11-19 | 3 | 2 | 2 | 20 |
| C7 | `map_repo` rewrites every map note via `write_note` which stamps `updated=now` → every commit hook churns committed `map/` in git and forces re-embedding all map notes. | operations.py:210-212, store.py:119-121 | 3 | 3 | 2 | 24 |
| C8 | Any `SCHEMA_VERSION` bump forces re-embedding every note (format version and schema version are conflated). | indexer.py:37-38 | 2 | 2 | 1 | 20 |
| C9 | `finder.find` shells out to `git ls-files` and Python-scores every path and every symbol row per call; no prefilter. | finder.py:96-105, :144-171 | 2 | 2 | 3 | 12 |
| C10 | `guard` re-parses the file once per rule (file × 12 practice rules). | guard.py:184-188 | 2 | 1 | 1 | 15 |
| C11 | Hashing embedder: 384 md5 buckets, TF only, no IDF → vector leg is a noisy duplicate of the lexical signal, so RRF double-counts term overlap and MMR diversifies over collision noise. Hybrid search without fastembed is **worse than keyword-only**. | embeddings.py:18-46, search.py:79-82 | 3 | 2 | 1 | 25 |

### D. Structure & code debt

| # | Finding | Where | I | R | E | Pri |
|---|---|---|---|---|---|---|
| D1 | `operations.py` is a god module: 1,492 lines, 12+ concerns, 29 local imports. Coach flags it as the #1 hotspot (churn 36 × complexity 1715). Seams already exist as `# ---- banner ----` comments. | operations.py (whole) | 4 | 3 | 3 | 21 |
| D2 | **No render layer**: 11 formatter pairs duplicated between `cli.py` and `server.py` (map, impact, connect, find, export, clean, consolidate, recipes, list_commands, stale, hooks_status); violation/unknown-import strings copy-pasted 5× / 3×. Coach: 84 % temporal coupling cli↔server. | server.py:53-265 vs cli.py:181-751; operations.py:943, :1371, cli.py:399, :799, server.py:193 | 4 | 3 | 2 | 28 |
| D3 | **No result types**: ops return 7 shapes (pydantic, list[pydantic], list[dict], untyped dict ×10, str, None, Optional). Adapters index dicts with string literals → renamed key = runtime KeyError. `clean` merges two differently-shaped dicts. | operations.py:177, :567, :597, :883, :929, :1033, :1058, :1384, :1467 | 3 | 3 | 3 | 18 |
| D4 | `TorsorPaths(root)→exists→load_config→Store` preamble copy-pasted **21×** in cli.py though `_load()` (cli.py:695) exists; `recipes` omits `load_config`. | cli.py:131…698 | 3 | 2 | 1 | 25 |
| D5 | Git subprocess wrapper reimplemented in 5 places; `_rel`-style relative-path helper in 6; `_is_git_repo` in 3. | operations.py:821, :846, :1126, :1136; hooks.py:191; export.py:22; coach/staleness.py:27; guard.py:206; deps.py:185; cartographer.py:247 | 2 | 2 | 1 | 20 |
| D6 | Defaults declared in 3 places each: primer `800` tokens, `connect` `max_hops=12`; `_BOOTSTRAP_ALLOC` fractions and `agent_rules(600)` hardcoded outside `BudgetConfig`. | cli.py:344/server.py:162/operations.py:391; cli.py:217/server.py:85/operations.py:597; operations.py:20-27, :260 | 2 | 2 | 1 | 20 |
| D7 | 16 call sites carry an unused `config`/`store` parameter "for symmetry" (`cleaner.apply`, `finder.find`, `impact`, `connect`, `check_drift`, …). | see agent inventory | 1 | 1 | 1 | 10 |
| D8 | `coach/` imports `db` and takes a raw `sqlite3.Connection`; `hubs` encodes schema tuple shapes. No read-model seam. Adding a coach check needs 6 edits (module, report import, chain, session_digest list, models comment, severity vocabulary). | coach/report.py:3-45, hubs.py:5, coupling.py:8, recommender.py:3 | 2 | 2 | 3 | 12 |
| D9 | `clients.py` keeps 3 parallel dicts + an 8-branch `if` chain; `practices.detect_languages` maintains a **second language↔extension registry** that will conflict with the planned `languages/` package. | clients.py:7-136, practices.py:427-441 | 2 | 2 | 2 | 16 |
| D10 | Dead code: `db.note_hashes`, `cartographer.scan_repo`, `cartographer._norm_module`, `CleanPlan.is_empty`; stale comment `config.py:35` "Placeholder for Phase 2"; `auto_handoff(session_id)` accepted and ignored. | db.py:94, cartographer.py:74, :289, cleaner.py:32, config.py:35, operations.py:1219 | 1 | 1 | 1 | 10 |
| D11 | 8 of 12 ADRs carry `rules: []`; guard enforces 4 rules total. ADR 0013 (multi-language) unwritten though spec/plan exist. | .torsor/architecture/decisions/ | 2 | 2 | 1 | 20 |

### E. Feature parity & CLI UX

| # | Finding | Where | I | R | E | Pri |
|---|---|---|---|---|---|---|
| E1 | **7 of 28 MCP tools have no CLI command** — the entire memory-write half: `recall`, `remember`, `handoff`, `update_active`, `bootstrap_session`, `get_intent`, `record_decision`. CLAUDE.md says "nearly every feature is both". | server.py:21-178 vs cli.py | 4 | 2 | 2 | 24 |
| E2 | Capability drift per surface: `find` (CLI `--files-only/--symbols-only` missing on MCP), `stale` (MCP lacks `unmark`/`strict`), `guard` (CLI lacks `--new-only`), `deps` (MCP has no failure signal), `map` (CLI can't do partial `paths`), `coach --dismiss` (no MCP). | cli.py:243, :465-467, :368; server.py:97, :184-216, :244 | 3 | 2 | 1 | 25 |
| E3 | `--json` on only 4 of 27 commands; flag var named `json_out` vs `as_json`; no shared `_emit()`. The CLI is the declared "cheap model" surface but emits prose. | cli.py:367, :436, :466, :652 | 3 | 2 | 2 | 20 |
| E4 | `root` redeclared 26× with 4 different help strings, no `-r`, no `TORSOR_ROOT` env fallback; should be a global callback option. | cli.py:43, :54…756 | 2 | 1 | 2 | 12 |
| E5 | Positional arg named `paths` / `files` / `paths` for the same concept (guard/deps/verify); MCP calls all three `files`. `strict` gets auto `--no-strict` while other flags don't. | cli.py:363, :408, :432, :365, :410, :467 | 2 | 1 | 1 | 15 |
| E6 | `hooks run <event>` is a free-form `str` (5 valid values in help only); `models --write x.json` overwrites the whole file while `--write x.md` merges a block; `rules --scoped` silently ignores `--write`/`--client`; `commands --add name=cmd` ad-hoc parsing. | cli.py:756, :672-680, :297-301, :611-627 | 2 | 2 | 1 | 20 |
| E7 | `server.py` captures `paths/store/config` once at startup: a long-lived server never sees `torsor.toml` edits; no `.torsor/` existence check → 28 tools that return empty strings; malformed config = raw pydantic traceback. | server.py:14-16 | 2 | 2 | 1 | 20 |
| E8 | `adopt_practices` over MCP returns `result["message"]` → success indistinguishable from "Unknown pack"; `guard.load_rules_by_note` swallows malformed `rules:` blocks with no diagnostic. | server.py:175, guard.py:38 | 2 | 2 | 1 | 20 |
| E9 | `doctor` has no `--json` and no per-check breakdown while `verify` has both; "empty" hints are printed on stdout (not pipe-safe). | cli.py:146, :600, :637 | 1 | 1 | 1 | 10 |
| E10 | Docs drift: CLAUDE.md says `torsor self-update` (command is `update`); README says "235 tests" and "328 tests" (actual 444), "v0.4 shipped" in roadmap; README "What's new" stops at v0.4; CHANGELOG `[Unreleased]` edit gate not released. | CLAUDE.md:25, :45; README.md:448, :452, :493, :207-230 | 2 | 1 | 1 | 15 |

### F. Tests

| # | Finding | Where | I | R | E | Pri |
|---|---|---|---|---|---|---|
| F1 | Only **one** test calls a tool through the MCP protocol (`call_tool("verify")`); every other server test asserts `list_tools()` names. The 27 tool bodies' formatting is untested. No stdio end-to-end test (`torsor mcp` as subprocess → `initialize`/`tools/list`/`tools/call`). `test_http_transport.py` only monkeypatches `FastMCP.run`. `read_resource` never tested. | tests/test_server*.py, tests/test_http_transport.py | 4 | 3 | 2 | 28 |
| F2 | Zero direct tests for `check_dependencies` (ops wrapper), `pre_push` (the one hook that can **block a push**), `_transcript_digest` (parses untrusted JSONL), `_scope_to_paths_glob` (decides whether a rule loads at all). No `CliRunner` tests for `deps`, `export`, `find`, `impact`. | operations.py:900, :1297, :1197, :321 | 3 | 3 | 1 | 30 |
| F3 | No property-based tests; `hypothesis` absent. The three hand parsers (`parse_frontmatter`, `extract_wikilinks`, `fts_search` MATCH) have only hand-picked examples. Only 3 `pytest.raises` in the suite. | store.py:32, :63; db.py:237 | 2 | 3 | 2 | 20 |
| F4 | `conftest.tmp_project`/`git_project` exist but a private `_store(tmp_path)` helper is redefined in **17 files** with three different `CLOCK` dates; `_git()` helper copy-pasted in 5 files (a missing `commit.gpgsign false` in any copy = fails on signing machines). ~50 substring asserts on human copy duplicated between cli/server. | tests/*.py | 2 | 2 | 2 | 16 |
| F5 | No coverage measurement, no `pytest-xdist` (suite is parallelizable: no chdir/env/wall-clock — its strongest property, keep it), no packaging test beyond `__version__` is a dotted string. | pyproject.toml:35, ci.yml | 3 | 2 | 1 | 25 |

### G. Docs

| # | Finding | Where | I | R | E | Pri |
|---|---|---|---|---|---|---|
| G1 | README is **two releases stale**: badges say v0.4 / 328 tests; three different test counts (235/328/444); "What's new" stops at v0.4; advertises the *unreleased* edit gate as shipped; "Once published to PyPI" though v0.4.0/v0.6.0 tags exist (v0.5.0 tag missing). | README.md:11-12, :38, :207-249, :262, :448, :452, :493 | 3 | 2 | 1 | 25 |
| G2 | `connect`, `verify`, `stale`, `clean`, `hooks*`, `hooks_status`, `find_files`, `get_model_policy`, `record_command`, `list_commands`, `recipes` are absent from the README and `docs/how-to-use.md` reference tables — everything from v0.5/v0.6 is undocumented for users. No test ties `@app.command`/`@mcp.tool()` to the README (the repo already does this pattern for clients in `test_clients.py:73`). | README.md:366-407, docs/how-to-use.md:137-162 | 3 | 2 | 1 | 25 |
| G3 | `docs/vibe-coding-guide.md` claims "you can run any of them from the CLI" — false for the five founding memory tools (E1). | docs/vibe-coding-guide.md | 2 | 2 | 1 | 20 |
| G4 | All 9 `docs/superpowers/plans/*.md` are checkbox-tracked and **nobody ever ticked a box** (checked 0–1 per plan, incl. phases shipped a year ago) → plans are misleading as status. The 2026-06-01 foundation spec's Prompts (`/torsor:onboard`, `/torsor:checkpoint`, `/torsor:review-drift`, `/torsor:coach`) and 2 of 4 resources (`torsor://architecture`, `torsor://map/overview`) were never built; coach spec §7 (`first_seen`/`last_shown`/`resolved`, escalation) and §6 `kinds` filter never built. Prior audit (2026-07-18) has 4 High items still open. | docs/superpowers/plans/, specs/ | 2 | 2 | 1 | 20 |
| G5 | README structure: 502 lines / 43 KB, quickstart at line 276, no troubleshooting link, no data-flow diagram (though `torsor export` generates a Mermaid one), inline second changelog, unverified emoji anchors. | README.md | 2 | 1 | 2 | 12 |
| G6 | Coach on this repo is **not clean** (README says it is): `dangling_link` false positives because map notes render docstring `[[wikilinks]]` literally, and `.claude/` is not in `DEFAULT_IGNORE` so the worktree under `.claude/worktrees/` is scanned as source. | cartographer.py:11, .torsor/map/modules/src__torsor_helper__cli.py.md | 2 | 2 | 1 | 20 |

### H. Packaging / CI

| # | Finding | Where | I | R | E | Pri |
|---|---|---|---|---|---|---|
| H1 | `uv.lock` is **git-ignored** and no runtime dep except `mcp` has an upper bound → a typer 1.0 / pydantic 3 release breaks CI and every fresh install with zero code change. No dependabot. | .gitignore:11, pyproject.toml:25-32 | 3 | 4 | 1 | 35 |
| H2 | `publish.yml` runs `uv build` → PyPI with **no test step and no `needs:` on CI** — a red commit can publish. No test installs the built wheel and runs `torsor --help`. | .github/workflows/publish.yml | 3 | 4 | 1 | 35 |
| H3 | CI: Python 3.11/3.12 only (no 3.13/3.14 though `requires-python >=3.11` uncapped); ubuntu only (hooks write `#!/bin/sh` + `chmod`, `shell=True` — Windows unverified and unclaimed). | ci.yml:9-14 | 2 | 3 | 1 | 25 |
| H4 | No type checker, no `py.typed`, no `__all__`; ruff only `E4,E7,E9,F` (no `I`, `B`); `ruff` unpinned via `--with ruff`. | pyproject.toml:69-72 | 2 | 2 | 2 | 16 |
| H5 | Release is manual in 3 places (`__version__`, tag, `gh release create --notes-file CHANGELOG.md` attaches the whole 23 KB changelog); v0.5.0 was documented but never tagged. | PUBLISHING.md:24-33 | 2 | 2 | 2 | 16 |
| H6 | No pre-commit config and **this repo does not run `torsor hooks install` on itself** — the flagship gates aren't in its own commit flow. No `SECURITY.md`/`CONTRIBUTING.md`. | repo root | 2 | 2 | 1 | 20 |

### I. Product gaps (grounded in code)

| # | Gap | Grounding | I | R | E | Pri |
|---|---|---|---|---|---|---|
| I1 | **Python-only code intelligence on `main`** — the spec's own "single largest adoption blocker". **Fully implemented and green on the unmerged branch `worktree-feat-multi-language-map`** (see Phase 5); the remaining effort is review + merge + release. | cartographer.py:204 | 5 | 3 | 1 | 40 |
| I2 | **Search filters exist in the core and are dropped at the adapters**: `hybrid_search(type_, kind, include_superseded)` → `recall(query, limit)`. No date-range filter at any layer though `notes.updated` is stored. "Only ADRs" / "what did we decide last week" is inexpressible. | search.py:62, operations.py:121, server.py:26 | 4 | 2 | 1 | 30 |
| I3 | **`doctor` is shallow**: 4 checks (dir, seed files, config parses). Doesn't report index freshness/schema, hashing-vs-fastembed (a silent recall-quality cliff), git availability, hook install state (`hooks_status` exists!), `torsor` on PATH for the hooks it wrote, map staleness, malformed ADR `rules:`. | cli.py:127-146 | 3 | 2 | 1 | 25 |
| I4 | **No `stats`/observability**: `note_count`, `op_totals`, `top_accessed`, `modules`, index size all exist and are unexposed. | db.py:106, :414, :435, :336 | 3 | 1 | 1 | 20 |
| I5 | **MCP prompts: zero**; resources: 2 of the 4 specified. Prompts are how MCP surfaces slash-commands in Claude Code/Cursor — cheapest UX win, already designed. | server.py:267-271 | 3 | 1 | 1 | 20 |
| I6 | `consolidate` computes **which** entries are duplicates and throws the list away (returns only a count). | operations.py:1060-1080, coach/mining.py:51 | 2 | 1 | 1 | 15 |
| I7 | **Config accepts typos silently**: no `extra="forbid"`; `guard_on_edit: str` not `Literal["off","advise","block"]`; no `torsor config` to print effective values; no `TORSOR_ROOT` env. | config.py:76, :99 | 3 | 3 | 1 | 30 |
| I8 | **Team/shared memory has no merge story**: two branches append to the same `memory/journal/<date>.md`; 67 committed map notes regenerate wholesale → conflicts on every concurrent `torsor map`. No `.gitattributes` merge driver (union for journals, regenerate for map). | store.py:160, .torsor/map/ | 4 | 3 | 3 | 21 |
| I9 | **No memory lifecycle** beyond `journal_retention_days`; no contradiction detection (ADR supersession is manual); Coach never shows "resolved" (spec §7 unbuilt). | cleaner.py, coach/state.py | 3 | 2 | 3 | 15 |
| I10 | **Memory and symbol graph are disconnected**: "which decisions/learnings mention this symbol" is the killer query this architecture uniquely enables and doesn't ship (`impact` is call-graph-only). | operations.py:567 | 4 | 1 | 3 | 15 |
| I11 | Guard has 4 static rule kinds; **no import-cycle detection** though `db.module_edges` makes it ~20 lines; no naming/placement/size rules; no pluggable checker. | guard.py:176-181, db.py:306 | 3 | 2 | 2 | 20 |
| I12 | Security hygiene: git-hook scripts interpolate `root` unquoted (`shlex.quote`); `.claude/settings.json` (usually committed) distributes "run whatever `torsor` is on PATH" to every collaborator (undocumented trust implication); `torsor update` has no confirmation/target-version display. | hooks.py:24-41, updater.py:40-53, cli.py:118 | 2 | 3 | 1 | 25 |
| I13 | No confirmation on any destructive op (`clean --apply`, `hooks install`, `update`); no interactive mode at all (`typer.confirm` unused). | cli.py | 2 | 2 | 1 | 20 |

---

## Part 2 — Phased roadmap

Ordering principle: ship the finished multi-language branch first (Phase 5, it is done and
rebasing it later would hurt) → stop the bleeding (data loss / security) → carve the seams that
make everything else cheap (render layer, result types, module split) → performance → correctness
→ parity/UX → hygiene → product bets. Each phase is independently shippable and keeps
`uv run --extra dev pytest -q`, `ruff`, and `torsor guard --strict` green. TDD per CLAUDE.md:
failing test first for every bug.

### Phase 0 — Safety fixes — **DONE (2026-09-20)**

> Shipped on `feat/safety-fixes`: A1, A2, A3, A4, A5, A6, A7, A8, I7, I12, G6, H1, H2, E10/G1,
> plus B3 which shipped earlier with the token-budget work. 25 regression tests; 569 pass, ruff
> and `torsor guard --strict` clean.
>
> **A9 was not a bug.** The audit read `merge_settings_hooks(data, root=".")` as wrong for a
> project whose `.torsor/` sits in a subdirectory. `.claude/settings.json` resolves under the
> same root, so Claude Code's cwd is that root and `"."` is correct. Verified, not assumed.
>
> Still open from this phase's neighbourhood: nothing. The original list follows for the record.

1. **A1** `install_hooks`/`uninstall_hooks`: on `json.loads` failure **abort with a message**, never write. Write via tmp+`os.replace`. Test: malformed settings.json is left byte-identical.
2. **A2** `merge_settings_hooks`: filter *hooks inside a group*, drop the group only when it becomes empty. Tighten `_SENTINEL` to a `command.startswith(...)`/regex-anchored check. Tests: mixed group keeps the foreign hook.
3. **A8/A9** `uninstall`: honour help text (`--local` = also); `install --local` removes prior global entries; pass the real `root` to `merge_settings_hooks`.
4. **A4/A5** Add one `paths.contain(root, p) -> Path | None` helper (reuse the containment already written in `pre_edit`, operations.py:1345-1352); use it in `guard.check_drift`, `_set_note_status`, `map_repo` note writes, `cartographer._scan(paths=)`.
5. **A3** `run_command`: keep `shell=True` (commands are shell lines by design) but (a) drop the MCP path — `verify(run_tests=True)` over MCP returns `skip` with a reason, matching the ADR 0009 "installers are CLI-only" logic; (b) document in a new ADR that command execution is CLI-only. Alternatively gate with `automation.allow_mcp_run_tests = false` default.
6. **A6** `mcp --http` on a non-loopback host requires `--allow-remote` (explicit opt-in); otherwise exit 2.
7. **A7** `clean --apply --deep` requires `--yes`; and move `coach_state.json` + `capture_state.json` out of `.index/` into `.torsor/state/` (git-ignored but not disposable) — see Phase 3.
8. **B3** Wrap the Coach digest and `_recent_journal` in the same `truncate_to_tokens` budget; add `budgets.practices_tokens`; cap `impact` callers and `verify` reasons by budget.
9. **I12** `shlex.quote(root)` in `post_commit_script`/`pre_push_script`; `torsor update` prints target version and asks `typer.confirm` unless `--yes`.
10. **I7** `TorsorConfig`/sub-models: `model_config = ConfigDict(extra="forbid")`; `guard_on_edit: Literal["off","advise","block"]`; `doctor` surfaces the validation error. Test: typo'd section fails loudly.
11. **G6** Add `.claude`, `.next`, `coverage`, `vendor`, `target`, `.turbo` to `DEFAULT_IGNORE`; escape `[[` in rendered map-note docstrings (`render_map`) so map notes stop creating dangling-link false positives. Re-run `torsor map --force && torsor coach` → clean.
12. **H1** Commit `uv.lock` (remove from `.gitignore`); add `.github/dependabot.yml` (pip + github-actions, weekly). **H2** `publish.yml`: add lint+test steps before `uv build`, then install the built wheel into a clean venv and run `torsor --help` / `python -c "import torsor_helper"`.
13. **E10/G1** Fix CLAUDE.md `self-update`→`update`; README badges/test counts/"What's new"→link to CHANGELOG; mark edit gate as unreleased or cut 0.6.1 with it; tag `v0.5.0` retroactively or note it in CHANGELOG.

### Phase 1 — Structural seams — **mostly DONE (2026-09-20)**

> Shipped on `feat/operations-split`, in the order below: PR 1 (hoist imports,
> un-shadow `guard`), PR 2 (`gitinfo.py`, which also fixed silently-skipped paths
> with spaces or non-ASCII names), PR 3 (CLI loader + `_emit` + `-r`/`TORSOR_ROOT`,
> which surfaced and fixed B12), PR 4 (the split: `operations/__init__.py` went
> 1560 → 108 lines across eleven modules, with ADR 0014 and the rescoped ADR 0002
> and 0011 rules), PR 6 (`render.py`), PR 7 (config ceilings, dead code).
>
> Measured effect: the Coach no longer lists `operations.py` among the repo's
> hotspots at all. 607 tests pass with and without `--extra languages`.
>
> **PR 5 (result dataclasses) is deliberately not done.** It would convert the
> ~10 untyped dict returns into models and touch 16 test files. The benefit is
> real but narrow — a renamed key becomes a type error instead of a runtime
> KeyError — and it is cleanly separable from everything above, which is what
> actually unblocked the rest of the plan. Do it when something else forces a
> pass over those call sites.
>
> **`--root` stayed a per-command option.** Promoting it to a callback option,
> as sketched below, would turn `torsor map --root X` into `torsor --root X map`
> and break every documented invocation. It gained `-r` and `TORSOR_ROOT` instead.

### Phase 1 — the original plan (for the record)

Goal: make the adapters genuinely thin and split `operations.py` with **zero behaviour change**.
Six PRs, each a green-suite commit series. Verified facts that shape the order: none of the 29
function-local imports in `operations.py` is a real cycle (nothing in core imports `operations`;
guard/hooks are forbidden to by ADR 0002/0012); 34 test files import `operations` and only
`test_auto_handoff.py` touches private names; `forbid_import` matches by dotted **prefix**, so a
`torsor_helper.operations/` *package* stays covered by every existing `target:
torsor_helper.operations` rule for free (an `ops/` sibling would silently escape them); there is
**no `.torsor/baseline.json`** and CI does not run `torsor guard`, so a rule whose scope stops
matching goes silently dead.

**PR 1 — hoist + rename (operations.py only, ~40 lines).** Move all 29 local imports to module
top (17 stdlib, 12 internal: finder :244, practices :757/:775, baseline :877/:887/:1337, deps
:904, coach.staleness :983, coach.trend :1087, hooks :1390/:1445/:1473). Rename the local
`guard = guard_run(...)` in `verify` (:942-950) to `guard_result` (it shadows the module).

**PR 2 — `gitinfo.py`.** Move verbatim: `_SOURCE_EXTS`→`SOURCE_EXTS`, `_rel_to_root`,
`_git_changed`→`changed_source_files`, `_git_changed_in_commit`→`commit_source_files`,
`_git_out`→`output`, `_git_head`→`head`. Keep the two existing exit-code semantics as-is
(`output()` returns `""` on non-zero; `changed_source_files()` uses stdout regardless). Keep
`_git_head`/`_git_changed` aliases in `operations` so `test_auto_handoff.py` is untouched. Add
`-z` / `-c core.quotePath=false` here once (B16). Follow-ups (not this PR): fold in
`hooks.resolve_hooks_dir`, `finder.py:98`, `coach/hotspots.py:19,30`, `coach/coupling.py:18`.
New `tests/test_gitinfo.py` on the `git_project` fixture.

**PR 3 — `cli.py` preamble dedupe (adapter only).** Replace the 21 copies with `_load(root)`
(moved above `init`); give it `config: bool = True` so `recipes`/`commands` (which skip
`load_config` today) stay byte-identical on a malformed `torsor.toml`; `hooks run` keeps its
silent-return variant. Then `--root` → global callback option with `-r` and `TORSOR_ROOT` (E4),
and one `_emit(result, as_json)` helper (E3).

**PR 4 — the split (one PR, ~11 commits, ADR edits in the first).**
- Commit A: `git mv operations.py operations/__init__.py`; edit **ADR 0002 rule 2** scope
  `src/torsor_helper/operations.py` → `src/torsor_helper/operations/*.py` (rules 1 and 3 need no
  change — prefix + fnmatch already cover the package); edit **ADR 0011**'s `forbid_pattern
  shutil\.rmtree` scope the same way (else it goes dead); add ADR 0002 rules forbidding
  `render.py`/`gitinfo.py` from importing `server`/`operations`; add a new ADR (0014 once the
  multi-language branch's 0013 is merged) with two `forbid_pattern` rules on
  `src/torsor_helper/operations/*.py`: `^from torsor_helper\.operations import ` and
  `^from \. import ` (submodules import siblings by full path, never the façade — the one new
  cycle risk). Run `torsor rules --scoped` and commit the regenerated `.claude/rules/torsor/`
  (Claude Code's `paths:` glob `*` does not cross `/`, so the explicit `operations/*.py` scope
  is required). Update CLAUDE.md and the comment at `hooks.py:9`. Guard = 0 over all files.
- Commits B–K, one module each in DAG order, moving functions **verbatim** and adding an
  explicit `from .<mod> import (...)` block + `__all__` entry to the façade each time:

  | Module | Receives |
  |---|---|
  | `operations/_shared.py` | `_EMBEDDER_CACHE`, `_embedder_for`, `_open_index`, `_log_op` |
  | `operations/commands.py` | `_CMD_RE`, `list_commands`, `record_command`, `run_command`, `recipes` |
  | `operations/decisions.py` | `_next_adr_number`, `_slug`, `_find_adr`, `record_decision`, `list_practices`, `adopt_practices` |
  | `operations/memory.py` | `_BOOTSTRAP_ALLOC`, `_RECENT_JOURNAL_FRACTION`, `bootstrap_session`, `_SESSION_START_HEADER`, `session_start_context`, `_recent_journal`, `recall`, `remember`, `update_active`, `record_handoff`, `get_intent` |
  | `operations/graph.py` | `map_repo`, `export_project`, `find_targets`, `impact`, `connect` |
  | `operations/prompt_blocks.py` | rules/primer/models block writers: `agent_rules`, `_write_managed_block`, `write_rules_block`, `_rule_line`, `_scope_to_paths_glob`, `write_scoped_rules`, `project_primer`, `write_primer_block`, `_CHEAP_OPS`, `_SMART_WORK`, `model_policy`, `model_policy_json`, `write_model_policy` (+ their marker constants) |
  | `operations/maintenance.py` | `recommend`, `dismiss_recommendation`, `check_staleness`, `_stale_notes`, `_note_rel`, `_set_note_status`, `clean`, `consolidate`, `_snapshot_complexity` |
  | `operations/gate.py` | `check_drift`, `new_drift`, `guard_run`, `check_dependencies`, `_verify_check`, `_verify_tests`, `verify`, `pre_push`, `_proposed_text`, `pre_edit` |
  | `operations/capture.py` | `_capture_state_path`, `_load_capture_state`, `_save_capture_state`, `_op_totals`, `_op_delta`, `_adrs_between`, `_read_md_section`, `_find_file_paths`, `_transcript_digest`, `auto_handoff`, `on_commit` |
  | `operations/hooks_ops.py` | `install_hooks`, `uninstall_hooks`, `hooks_status` (settings.json I/O moved verbatim; dedupe into `hooks.read_settings/write_settings` in a follow-up — ops→hooks direction is ADR-legal) |

  Edges are all forward (`memory/graph/prompt_blocks/gate/maintenance → _shared`;
  `prompt_blocks,gate → commands`; `gate → maintenance`; `capture → gitinfo, decisions, memory,
  graph, maintenance`; `hooks_ops → hooks, capture, gitinfo, decisions`) — acyclic.
- Final commit: façade = imports + `__all__` + a commented compat block re-exporting the 5
  privates `test_auto_handoff.py:29-32,53` uses; add `tests/test_operations_package.py` that
  `importlib.import_module`s each submodule cold (catches façade-import cycles pytest's import
  order can hide); `torsor map` + `torsor clean --apply` to drop the orphaned
  `src__torsor_helper__operations.py.md`. Keep op-log strings verbatim (`find_targets` logs
  `"find_files"`, `write_scoped_rules` logs `"get_rules"` — they feed `recipes`/`_CHEAP_OPS`).

**PR 5 — result models in `models.py`** (pydantic, the file's convention), one commit per op,
fields in today's dict order so `json.dumps(model_dump())` is byte-identical; adapters + tests
in the same commit. Order by blast radius: `AdoptResult`, `ConsolidateStats`, `CleanStats`,
`StalenessResult`, `CommitResult`, `MapStats`, `ImpactResult`, `ConnectResult`,
`GuardResult`/`PushVerdict`/`EditVerdict`, `VerifyCheck`+`VerifyVerdict`,
`HooksInstallResult`/`HooksStatus`. Leave as dicts: `model_policy_json` (it *is* JSON),
row-shaped lists from `finder`/`db`/`deps`, `export_project`. Tests needing subscript→attribute:
`test_verify_op`, `test_connect`, `test_map_fingerprint`, `test_impact`, `test_practices`,
`test_on_commit`, `test_edit_gate`, `test_clean_op`, `test_consolidate_op`, `test_operations`,
`test_stale_op`, `test_map_repo(_partial)`, `test_cli_verify`, `test_server_verify`, `test_cleaner`.

**PR 6 — `render.py`** (after models, written once against attribute access). Move only the
per-item line formatters — the adapter pairs are *not* identical (cli `->` vs server `→`,
`- ` vs two-space indent, different framing verbs), so adapters keep framing and call:
`violation_line` (cli:399, :799, server:193, verify:943 — `pre_edit`:1371 uses a different
format, leave it), `caller_line`, `path_chain`, `find_line`, `recipe_line`, `command_line`,
`dep_line`, `stale_line`, `recommendation_line(arrow=…)`, `clean_summary(verb)`,
`consolidate_summary`, `map_summary`. `tests/test_render.py`; the existing `test_cli_*` /
`test_server_*` substring assertions are the regression net.

**PR 7 — knobs & dead code.** Config-backed defaults (D6): `BudgetConfig.primer_tokens`,
`rules_tokens`, bootstrap allocation fractions; `IndexConfig.connect_max_hops`; delete the
triplicated literals. Delete dead code (D10); remove unused "symmetry" params (D7).

Riskiest spots to watch: façade-import cycle at package init (mitigated by the sibling-import
rule + cold-import test); `_EMBEDDER_CACHE` must live in `_shared` only (all four callers
`recall`/`map_repo`/`consolidate`/`recommend` route through it — never copy the dict); silent
dead ADR scopes (add a CI step `torsor guard --strict $(git ls-files 'src/**/*.py')` and a
dogfood test that runs `guard.violations_for_file` against the repo's real ADRs); after the
split, `monkeypatch` on the façade no longer intercepts sibling-to-sibling calls (no test relies
on it today — document in the façade docstring).

### Phase 2 — Performance — **DONE (2026-09-21)**

> Shipped on `feat/index-performance`. `recall` 7 650 ms → 482 ms, `map_repo` cold
> 163 960 ms → 25 514 ms, on a generated 5 000-note corpus (`tests/bench/`).
>
> **The audit's predictions were mostly wrong, and that is the finding worth keeping.**
> C1/C2 named search and the vector scan; profiling put 5.8 s of an 11.8 s recall in
> `store.iter_note_paths`, which called `Path.resolve()` once per note, and 24 s of a
> 61 s cold map in `store.tier_for_path`, which did the same thing four times per note.
> Neither appears anywhere in this document. The search fixes (C1), the vector matrix
> (C2), the indexes (C3), the connect short-circuit (C4), the slug index (C5), the map
> write skip (C7) and the version split (C8) all shipped too, and together they are
> worth less than the two syscall-per-note bugs profiling found.
>
> Two new invariants a contributor can break silently, both in CLAUDE.md: `db.connect`
> trusts the `SCHEMA_VERSION` stamp, and `INDEX_FORMAT_VERSION` is what costs a re-embed.
>
> **C6 (Coach caching) and C11 (gate the vector leg on the hashing embedder) are not done.**
> C6 never showed up as a cost on the bench, so there is nothing to justify the churn yet.
> C11 is not a performance question any more now that `cosine_search` is a matrix multiply —
> it is a retrieval-quality decision about whether the hashing fallback's vectors are worth
> fusing at all, and it belongs with the other quality work in Phase 3.

### Phase 2 — the original plan (for the record)

Add `tests/bench/` (pytest-benchmark or a plain timing script) with generated fixtures of
5k notes / 20k symbols so every item below has a number.

1. **C1** `search.py`: apply `type_/kind/superseded` filters in SQL; fetch rows with one `IN`
   query; run MMR on `~4×limit` candidates; compute snippets **after** `[:limit]`; batch
   `get_vectors`.
2. **C2** `cosine_search`: store L2-normalized float32 blobs; load the matrix once per
   connection (cache keyed on a `vectors_generation` meta counter) and do `matrix @ q`.
   Gate `reindex` in `_open_index` on a cheap `store` fingerprint (mtime/size scan already
   exists in `note_stats`) so unchanged corpora skip it; gate `reresolve_edges` on
   `pending or deleted`.
3. **C3** Add the five indexes in `_create_schema` (bump `SCHEMA_VERSION`, see B2 fix).
4. **C4** `connect()`: read `meta.schema_version` first; run `_create_schema` only when missing/old;
   `PRAGMA synchronous=NORMAL`. `_log_op`: reuse the caller's connection when one is open.
5. **C5** Hoist `_note_paths` → `{slug: path}` dict out of the per-note loop; switch `fts` to an
   external-content table keyed by `notes.rowid` so DELETE/`body_of` are rowid lookups.
6. **C7** `map_repo`: compare rendered body to existing note body and skip the write (and the
   `updated` stamp) when identical. Stops map/ churn in git and re-embedding on every commit.
7. **C6** Coach: one `SourceCache` per `recommend()` run (path → source/tree/complexity) shared by
   hotspots/trend/deps; one `git log` parse shared by hotspots+coupling; bound history with
   `--since` from a new `coach.history_days` (default 180).
8. **C11** When `embedder.name == "hashing"`, skip the vector leg of RRF and MMR (honest
   keyword-only fallback). Optionally add IDF weighting later.
9. **C8** Split `indexed_schema` (embedding/FTS input format) from DB `SCHEMA_VERSION` so index-only
   changes don't re-embed.

### Phase 3 — Correctness (≈1 week)

1. **B1** Make the index-derived graph explicit: `map_repo(paths=…)` refuses (or auto-falls back to
   a full scan) when `meta.map_fingerprint` is missing/mismatched; `cleaner` orphan detection
   requires a fresh fingerprint or performs its own `iter_source_files` scan (source of truth =
   files, not `db.modules()`).
2. **B2** `connect()` reads the stored version; if `< SCHEMA_VERSION` → drop and rebuild the DB file
   (the index is disposable — say so). Document in CLAUDE.md honestly.
3. **A7 (state)** New `TorsorPaths.state_dir = .torsor/state/` for `coach_state.json`,
   `capture_state.json`; git-ignore it via `init`; `clean --deep` leaves it alone (ADR 0011
   amendment). Keep `op_log`/`path_access` in the index but document they're lossy.
4. **B4/B5** `store.py`: parse wikilinks into `(slug, section, alias)`, normalize `dir/slug`;
   `_resolve_slug` prefers exact-relative match, then unique basename, and returns
   `ambiguous=True` otherwise; staleness ignores alias/section forms; Coach gets an
   `ambiguous_link` info rec.
5. **B6** Replace `fnmatch` with a `/`-aware matcher (`PurePath.full_match` on 3.13, else a
   translated regex where `*` ≠ `/` and `**` spans dirs). Add a migration note: existing scopes
   like `src/torsor_helper/*.py` become literal — fix ADR 0002 scope to `src/torsor_helper/**/*.py`
   in the same PR.
6. **B7/B8** `read_note` → `utf-8-sig`; declare `kind`, `rules`, `supersedes` on `Frontmatter`;
   coerce scalar `tags`/`links` to one-element lists instead of discarding the frontmatter.
7. **B9** Store note paths repo-relative POSIX in the index (`as_posix()` at the indexer boundary);
   resolve to absolute on read. (Also fixes "moved checkout" invalidation.)
8. **B10/B11/B12** `auto_index=false` → never reindex implicitly; `verify` passes `files` to
   staleness; `guard` CLI: `--new-only` flag, exit code and JSON both reflect `new`; validate
   `--severity` and `hooks run <event>` as `Enum`s; `--mark`/`--unmark` mutually exclusive.
9. **B13** Persist embedder identity per *successful* embed; on fastembed failure keep the stored
   identity and skip re-embedding (serve stale vectors + warn) rather than thrashing.
10. **B14** `export` writes the Mermaid diagram to `map/dependencies.md` (its own note), not into
    `overview.md`.
11. **B15** Cartographer: walk `ast` for imports (match guard/deps semantics) and record nested
    defs with a dotted owner; keep ADR 0004's "two reliable cases" for *resolution*.
12. **B17** Validate `importance_floors` keys (case-insensitive) in `IndexConfig`.

### Phase 4 — Parity & CLI UX (≈3 days after Phase 1)

1. **E1** Add `torsor recall`, `remember`, `handoff`, `active` (update_active), `bootstrap`,
   `intent`, `decision` commands — thin wrappers over the same ops + renderers.
2. **E2** Align option sets per feature (table in finding E2); add `dismiss` to MCP `recommend`
   or a `dismiss_recommendation` tool; `check_dependencies` returns a structured result with
   `ok`.
3. **E6** `models --write`: separate `--write-json` from `--write` (block merge); `rules --scoped`
   errors if `--write`/`--client` given; `commands --add NAME CMD` as two args.
4. **E7** `build_server`: check `.torsor/` exists (return one clear error tool result), reload
   config lazily per call (cheap: TOML mtime), wrap config errors in the `doctor` message.
5. **E8** `adopt_practices` returns `{ok, message}` over MCP; `load_rules_by_note` collects parse
   errors and `doctor` reports them.
6. **E9** `doctor --json` with per-check rows (reuse `_verify_check` shape).
7. **I4** Add `torsor stats` (+ `stats` MCP tool): notes per tier, index size, symbols/edges,
   map fingerprint age, embedder in use, op totals, top accessed — reuses `db.note_count`,
   `db.op_totals`, `db.top_accessed`, `db.modules`, `cleaner._size`.
8. **I3** Deepen `doctor`: index schema/freshness, embedder (warn on hashing fallback), git
   available, `hooks_status`, `torsor` on PATH, map fingerprint vs repo, malformed ADR `rules:`
   (from E8), config validation (from I7). All checks already exist as functions.
9. **I2** Thread `type_`, `kind`, `include_superseded` through `ops.recall` → `recall` MCP tool
   and `torsor recall`; add `since: str | None` (ISO date) filter in `hybrid_search`/`recall.py`
   on `notes.updated`.
10. **I5** Register the four MCP prompts from the foundation spec (`onboard`, `checkpoint`,
    `review-drift`, `coach`) as thin `@mcp.prompt()` wrappers over existing ops; add
    `torsor://architecture` and `torsor://map/overview` resources.
11. **I6** `consolidate` returns and renders the duplicate list (first N with counts).
12. **I11** New guard rule kind `forbid_cycle` over `db.module_edges` (Tarjan SCC; report one
    violation per cycle with the member list); document in the rules reference.

### Phase 5 — Multi-language map: **review and merge, it is already built**

The audit found the feature "not started" on `main`, but branch `worktree-feat-multi-language-map`
(worktree `.claude/worktrees/feat-multi-language-map/`, untracked in git status) contains the
**complete implementation**: 21 commits on top of `main` HEAD (`e15cc6a`, 0 behind), a
`languages/` package (registry, python, javascript, go, treesitter), Phase-2 `deps` for JS/TS/Go,
ADR 0013, `[languages]` extra, `__version__ = "0.7.0"`, +3,131/−777 lines, 12 new test files.
Verified today in the worktree: tests green **with and without** `--extra languages`,
`torsor guard --strict` clean, ruff clean. This is the highest-value single action in the plan.

> **Status: DONE (2026-09-20). Reviewed, two blocking bugs fixed, merged into `main`.**
>
> The review found two silent correctness bugs that the branch's own green suite
> missed, both reproduced by hand before fixing:
>
> 1. **A JS/TS file at the repo root never resolved its own references.** A file's
>    key came from its path and its importers' key from the import specifier, and
>    the two only met when the path contained a `/`. A flat repo reported
>    `impact = 0` and `refs = 0` with no error. The ambiguity is real — `pkg.go`
>    is both a plausible Python import target and a plausible root-level Go file,
>    and no string rule separates them, so the reviewer's proposed string fix was
>    wrong and broke a passing test. Resolved by the caller instead: `norm_path`
>    for a file path (always strips), `norm_module` for a possibly-dotted key
>    (does not).
> 2. **Go's cross-file resolver was sticky**, skipping edges that already had a
>    `resolved_module`, so the post-commit partial map left a moved same-package
>    symbol pointing at the file it had left. Partial gave `pkg.a` where a full
>    remap gave `pkg.b`, violating ADR 0008 with a wrong answer. It now
>    re-resolves every Go edge.
>
> Also folded in: `practices.py` was missing `.cjs` (the D9 two-registry drift,
> now real), and the spec's example scope `src/**/*.ts` cannot match
> `src/index.ts` under `fnmatch` (B6), corrected to `**/*.ts`.
>
> Three regression tests added. 532 tests pass with and without `--extra
> languages`, ruff clean, `torsor guard --strict` clean. Remaining for a release:
> tag `v0.7.0` after H2 hardens `publish.yml`, and announce the polyglot map in
> the README (G2).

Steps:
1. Run `/code-review` (or a reviewer agent) on `main..worktree-feat-multi-language-map` with
   the spec as the contract; pay attention to B6 (fnmatch `**` — check how the branch's
   `forbid_import`-on-TS tests scope rules; if they use `**/*.ts` the branch may have fixed or
   sidestepped it), to D9 (`practices.detect_languages` vs the new registry — the branch touches
   `practices.py`), and to `db.py` changes (+19: check whether `SCHEMA_VERSION` was bumped for
   the persisted edge `hint`).
2. Push the branch, open a PR, let CI run (add the `--extra languages` matrix axis in the same
   PR per the plan's "Packaging & CI" section if the branch didn't).
3. Merge, tag `v0.7.0`, release (after H2 hardens `publish.yml`), update README/docs (G2) so the
   polyglot map is actually announced.
4. Then `git worktree remove` the stale worktree and delete `feat/clean-gc` if merged.

Ordering note: Phase 5 can go **first**, before Phase 0/1 — it is finished work, and merging it
before the `operations.py` split avoids a painful rebase (the branch touches `operations.py`
+52 lines). Recommended order: **5 → 0 → 1 → 2 → 3 → 4 → 6 → 7**. Phase 5 is done; the token-budget work (B3, D11) shipped early on user request and is merged.

### Phase 6 — Tests, CI, docs hygiene (continuous, S each unless noted)

Tests (F):
1. **F1** One real MCP round-trip test per tool via `server.call_tool(...)` asserting the
   rendered text (after Phase 1 these become renderer golden tests + a thin per-tool smoke).
   One stdio end-to-end test: spawn `uv run torsor mcp` in a `tmp_project`, speak JSON-RPC
   `initialize` → `tools/list` → `tools/call recall`. One real HTTP test: start `--http` on an
   ephemeral port in a thread, `POST` a `tools/list`.
2. **F2** Direct tests for `check_dependencies`, `pre_push` (blocking + non-blocking),
   `_transcript_digest` (malformed JSONL never raises), `_scope_to_paths_glob`; `CliRunner`
   tests for `deps`/`export`/`find`/`impact`.
3. **F3** Add `hypothesis` to `dev`; property tests: `parse_frontmatter` never raises and
   round-trips through `write_note`; `extract_wikilinks` on arbitrary text; `fts_search` never
   raises `OperationalError` for any query string.
4. **F4** Promote the `_store(tmp_path)` and `_git()` helpers into `conftest.py` fixtures
   (`store`, `git_repo`) with **one** `FIXED_CLOCK`; migrate files opportunistically (M).
5. **F5** `dev` extra gains `pytest-cov`, `pytest-xdist`, pinned `ruff`; CI runs
   `pytest -n auto --cov=torsor_helper --cov-fail-under=<current>` and uploads the report.
   Suite target: < 10 s wall.

CI / packaging (H):
6. **H3** Matrix: Python 3.11–3.14 × ubuntu + macOS; a Windows job that runs the suite with
   git-hook tests marked `skipif(sys.platform == "win32")` until hooks are ported (and
   `install_hooks` refuses on Windows with a clear message meanwhile — I-D20).
7. **H4** Add `py.typed`; `mypy --strict` (or `pyright`) on `src/` in CI, starting with
   `check_untyped_defs` and ratcheting; ruff `select` += `I`, `B`, `UP`.
8. **H5** Tag-driven release workflow: `git tag vX.Y.Z` → verify `__version__` matches → run
   CI → build → slice the matching CHANGELOG section into the GitHub Release → publish.
9. **H6** `.pre-commit-config.yaml` (ruff, ruff-format, `torsor guard --strict`); run
   `torsor hooks install` on this repo (dogfood the auto-capture layer); add `SECURITY.md`
   (disclosure channel + the `--http` and settings.json trust notes from I12) and
   `CONTRIBUTING.md`.

Docs (G):
10. **G2** Add `tests/test_docs_surface.py`: every `@app.command` name and every `@mcp.tool()`
    name must appear in README + `docs/how-to-use.md` (same pattern as `test_clients.py:73`).
    Then fill the gaps it reports (connect/verify/stale/clean/hooks/find_files/…).
11. **G5** README restructure: badges → 5-line pitch → install → quickstart → "connect your
    agent" → feature tour (link-outs) → link to CHANGELOG/roadmap. Embed the `torsor export`
    Mermaid diagram + a short data-flow diagram (Markdown → indexer → SQLite → search → MCP).
    Add "Troubleshooting" that links `docs/how-to-install.md` and the FAQ.
12. **G4** Decide the fate of `docs/superpowers/plans/*`: either tick boxes retroactively and
    add a `Status:` line at the top of each spec (done / partial / superseded by ADR NNNN /
    not started) or move shipped plans to `docs/superpowers/archive/`. Add a `Status:` line
    to the 2026-07-18 audit report pointing at this plan.

### Phase 7 — Product bets (each is its own spec + ADR; order by user demand)

1. **I8 Team memory**: `torsor init` writes `.gitattributes` with `merge=union` for
   `memory/journal/*.md` and a `torsor-map` merge driver (regenerate on conflict) for
   `map/**`; `torsor merge` helper for `active/*.md`. Journal files gain a per-author or
   per-branch suffix option (`memory.journal_partition = "date" | "date-author"`).
2. **I10 Memory ↔ symbol graph link**: index `symbols`-mentions inside notes (backticked
   identifiers that match `symbols.name`) into a `note_symbols` table; `impact` and
   `get_intent` gain a "Decisions & learnings mentioning this symbol" section; `recall`
   gains a `symbol=` filter.
3. **I9 Lifecycle**: implement coach spec §7 (`first_seen`/`last_shown`/`resolved`,
   auto-clear, gentle escalation, "fixed since last time" digest line); a `contradiction`
   coach check that flags two active `type: decision` notes with near-duplicate vectors and
   opposite polarity keywords (`never`/`always`, `use`/`don't use`) — advisory only, precision
   over recall per ADR 0010.

---

## Part 3 — Verification (end-to-end, every phase)

```bash
uv run --extra dev pytest -q                 # all green, count goes up
uv run --with ruff ruff check src tests
uv run torsor guard --strict                 # dogfood: ADR layering still holds after the split
uv run torsor doctor && uv run torsor coach  # hotspot list should shrink after Phase 1
uv run torsor map --force && git status --short .torsor/map   # Phase 2.6: no churn on re-run
```

Phase-specific:
- Phase 0: new tests for malformed `settings.json` (byte-identical after install), mixed hook
  group, `../` path rejection in `check_drift`, `--http` non-loopback exit code, `clean --deep`
  without `--yes` refuses.
- Phase 1: no test file changes except imports; renderer golden tests; `git diff --stat` on
  `cli.py`/`server.py` should be net-negative by several hundred lines.
- Phase 2: `tests/bench/` numbers before/after; target recall p50 < 50 ms on 5k notes with hashing
  embedder; `map_repo` twice in a row = zero writes.
- Phase 3: Windows-style path test via `PureWindowsPath`; wikilink alias/section fixtures;
  fnmatch regression tests using this repo's own ADR scopes.
- Phase 5: CI matrix with and without `--extra languages` (per the plan).

## Out of scope / deliberately not recommended

- Async rewrite of the MCP server (prior audit I-19): FastMCP handles sync tools in a threadpool;
  the real cost is the per-call reindex (C2), not sync/async.
- ANN/HNSW vector index: not needed below ~50k notes once C2 lands; revisit with sqlite-vec later.
- Replacing stdlib `ast` for Python (ADR 0003 stands; multi-language adds tree-sitter *beside* it).
- Migrating to `mcp` 2.x `MCPServer`: separate deliberate task; `mcp<2` pin is correct today.
