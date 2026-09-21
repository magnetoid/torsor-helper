# Changelog

All notable changes to **torsor-helper** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/); the project is pre-1.0 and ships
in numbered phases (see the [roadmap](README.md#️-roadmap)).

## [Unreleased]

### 🔗 `impact` now tells you what was *decided* about a symbol, not just what calls it
torsor kept two graphs and never connected them: `[[wikilinks]]` link notes to notes, `symbol_edges` links code
to code, and nothing linked a decision to the function it was about. So an agent could see every caller of a
function and none of the recorded reason it looks the way it does — which is the one question this
architecture is uniquely able to answer.

- **`torsor impact <symbol>` and the `impact` MCP tool** now list the decisions, learnings and handoffs that
  name the symbol in backticks, alongside the callers. The two halves are independent: a symbol nothing calls
  can still be the one the team argued about, and that renders correctly.
- **`get_intent <topic>`** gains what was recorded about that topic — including journal entries, which its
  list of ADR titles never reached.
- **`torsor recall <query> --symbol <name>`** (and `symbol=` on the MCP tool) keeps only notes that mention
  that code symbol.

Mentions are extracted unfiltered and joined at query time, which is the whole design (ADR 0016). Filtering
them against the symbol table while indexing would have tied the feature to the order the two indexes were
built in — `reindex` screens on `(mtime, size)`, so a note written before the first `torsor map` would have
been scanned once, found no symbols, and never been looked at again. Map notes contribute nothing: they are
rendered *from* the symbol table, so their mentions are that table restated.

Existing indexes are backfilled on the next reindex **without re-embedding** — the mention table carries its
own format stamp rather than borrowing `INDEX_FORMAT_VERSION`, which would have re-embedded the whole corpus
to populate a regex result.

### 🤝 Two branches can now write `.torsor/` at the same time
Committing `.torsor/` is what makes it *team* memory rather than one developer's cache — and it was also what
made two branches collide. Both sides append to `memory/journal/<date>.md`, and `auto_map_on_commit` makes
every commit regenerate notes under `map/`, so any two branches that touched code conflicted across dozens of
derived files. Neither conflict deserved a human.

- **`torsor init` writes `.torsor/.gitattributes`** (committed; a managed block that leaves your own lines
  alone). Journals get git's built-in `union` merge, which keeps both sides' entries — this half needs no
  setup at all and covers the common case for everyone the moment the file is committed.
- **Journal headers no longer carry the wall clock.** A journal is stamped with its own date, so two branches
  that both start the day's file write a byte-identical header. Without that, the union merge unioned the
  frontmatter too and left a duplicate `created:`/`updated:` pair inside the `---` block on every merge. The
  date is also the truer value: the stamp was never refreshed on append, so it only ever meant "this day".
- **`torsor merge install`** registers a `torsor-map` merge driver in this clone. Map notes are derived, so
  the driver keeps yours and queues the note; the next `torsor map --force` rebuilds it from source.
- **`torsor merge status` and `torsor doctor` report the half that can go missing.** Git does *not* warn when
  a committed attributes file names a driver your clone never registered — it silently falls back to the
  ordinary text merge, which looks exactly like having configured nothing.
- **New `memory.journal_partition = "date-author"`** gives each git identity its own journal file, for teams
  where union merges get noisy. The date stays the leading token in the filename, because `clean` reads the
  retention date out of the stem — and parsing the whole stem would have switched journal expiry off in
  silence.

See ADR 0015. Registering a driver writes to `.git/config`, so it is CLI-only, the same rule as the hook
installers (ADR 0009) — and machine-checked the same way.

- **`torsor coach` no longer reads the whole git history, twice.** Churn and temporal coupling each walked
  every commit ever made, so the Coach got slower every year regardless of how much code there was — and a
  file that was hot three years ago is not the signal either check looks for. New `coach.history_days`
  (default 365; `0` disables the bound). Both also moved onto the shared `gitinfo` wrapper, so they stop
  silently skipping paths with spaces or non-ASCII names.

### ⚡ Performance: recall was 7.6 s on a 5 000-note project, and is now under half a second
Measured, not guessed. A new `tests/bench/` builds a deterministic 5 000-note, 200-module corpus so every
number below is reproducible, and each fix was picked by profiling — every assumption carried in from the
audit pointed somewhere else.

| path | before | after |
|---|---:|---:|
| `recall` (warm) | 7 650 ms | 482 ms |
| `recall` (cold, builds the index) | 14 273 ms | 495 ms |
| `recall` (filtered by type) | 8 949 ms | 495 ms |
| `map_repo` (cold) | 163 960 ms | 25 514 ms |
| `map_repo` (unchanged repo) | 198 ms | 73 ms |
| `get_intent` | 24 ms | 10 ms |
| `connect` | 132 ms | 65 ms |
| `find` (fuzzy) | 2 776 ms | 1 567 ms |

- **The biggest cost was not in search.** `store.iter_note_paths` called `Path.resolve()` — a syscall — once
  per note just to test whether the note sat inside `.index/`, and `reindex` walks it on every recall: 5.8 s
  of an 11.8 s recall. It prunes during traversal now, the way `cartographer.iter_files` already did.
  `store.tier_for_path` had the same shape, resolving four anchor paths per note inside `read_note`: 24 s of a
  61 s cold map. The anchors are resolved once per project root, and the usual caller matches without touching
  the filesystem at all.
- **Wikilink resolution was quadratic.** `_resolve_slug` scanned every note path once per distinct slug, over
  every edge, on every reindex, and `replace_edges` ran a full `SELECT` of all paths per note indexed. A
  `SlugIndex` built once replaces both; a slug containing `/` keeps the scan, because it matches a path
  *suffix* rather than a basename. The healing pass now runs only when the note set actually moved.
- **Search did work it then threw away.** MMR ran over every hit although only `limit` survive it (a 4×
  shortlist now, over pre-normalized vectors), and a snippet — an FTS lookup plus a scan of the body — was
  built for every candidate before the cut rather than for the handful shown. `note_row` and `get_vectors`
  were N+1; both batch now. Vectors are stored L2-normalized, so `cosine_search` is one matrix multiply
  instead of a Python loop that re-normalized each row.
- **`db.connect` ran the full schema pass on every open** — ten `CREATE`s, two `PRAGMA table_info`, a meta
  write and a commit — so every CLI command and every recall did a write transaction before any read. It
  trusts the version stamp now. The trade-off is documented in the code: **a schema change must come with a
  `SCHEMA_VERSION` bump**, where an unbumped one used to be absorbed silently. `PRAGMA synchronous=NORMAL`
  for the same reason (WAL already survives a process crash).
- **`map_repo` rewrote every module note on every run**, and `write_note` stamps `updated` from the clock — so
  the post-commit hook churned ~170 committed files after a one-file change *and* changed their content
  hashes, which made the next reindex re-embed all of them. Identical renderings are left alone.
- **Seven missing indexes** (`edges(src)`, `edges(target_path)`, `symbols(module)`, `symbols(name)`,
  `symbol_edges(resolved_module, referenced_name)`, `symbol_edges(module)`, `notes(type, kind)`) and an
  `fts_map`, so a body lookup by path is a rowid hit rather than a scan of a table whose `path` column is
  deliberately `UNINDEXED`. **`SCHEMA_VERSION` 7 → 8**; the index is disposable, so the bump just rebuilds.
- **A DDL change no longer re-embeds the corpus.** The re-embed trigger was tied to `SCHEMA_VERSION`, so
  adding an index forced every note through the embedder. A separate `INDEX_FORMAT_VERSION` now governs it
  and names what actually goes into the index: the breadcrumb, the FTS title, the embedding input.
- Frontmatter parsing uses libyaml's `CSafeLoader` when PyYAML was built with it (same grammar, C speed),
  falling back to the pure-Python loader otherwise.


### 🔒 Safety pass: the operations that touch files torsor does not own
- **`hooks install` could replace a user's entire `.claude/settings.json`.** Claude Code tolerates comments and
  trailing commas; `json.loads` does not, and on a parse failure the code fell back to `{}` and wrote the merge
  result — losing the user's permissions, env and model. Install and uninstall now abort and leave the file
  byte-identical; writes go through a tmp file and `os.replace`.
- **It also deleted foreign hooks.** Ownership was decided per hook *group*, and a group counted as torsor's if
  any hook in it matched, so a group holding one torsor hook and one of yours lost yours. Filtering now happens
  inside the group. Ownership is anchored too: a command must *be* a torsor invocation, not merely mention one
  (`my-wrapper --then 'torsor hooks run …'` is yours, and stays).
- `hooks uninstall` cleans **both** settings files — it used to clean one and leave the other firing — and
  `install --local` clears a prior global install instead of doubling every hook.
- Git-hook scripts `shlex.quote` the project root instead of interpolating it into a double-quoted shell string.
- **Every caller-supplied path is contained to the project root** (new `paths.contained`). `check_drift` and
  `verify` are MCP tools that take a file list, so an absolute path or a `../` escape used to be read and matched
  against the ADR rules — and a `forbid_pattern` rule reports the line it matched on, which makes it a read
  oracle. `stale --mark`, `map_repo`'s note writes and the cartographer's explicit-paths mode were equally open.
- **Running the project's recorded commands is CLI-only.** `verify(run_tests=True)` reached `shell=True`
  execution of `.torsor/commands.md` over MCP; that parameter is gone from the tool.
- `mcp --http` **refuses** a non-loopback host without `--allow-remote` (it used to warn and serve anyway);
  `clean --apply --deep` requires `--yes`; `torsor update` confirms before replacing the running binary.
- **A typo in `torsor.toml` is now an error.** Every config model forbids unknown keys and `guard_on_edit` is a
  `Literal`, so `[automaton]` or `guard_on_edit = "blok"` fails loudly; `doctor` prints the file and the detail.

### 🗂 Non-derivable state left the disposable index
- Coach dismissals and the auto-handoff watermark moved from `.torsor/.index/` to `.torsor/state/`. `clean --deep`
  removes the index wholesale — correctly, since everything else in it rebuilds from Markdown — and was therefore
  silently un-dismissing every recommendation and making the next handoff replay the whole history. Migration
  happens on read, and `.torsor/.gitignore` is updated in place for projects scaffolded before this existed.

### 🔧 Build & CI
- **`uv.lock` is now committed.** Every runtime dependency except `mcp` was unbounded and the lockfile was
  git-ignored, so a fresh resolve could break CI and every new install with no code change. Dependabot opens the
  update PRs.
- **A GitHub Release no longer publishes an untested commit.** `publish.yml` gained a `verify` job (lint, both
  test matrices, `torsor guard --strict`, and a check that the tag matches the packaged version) that the publish
  job now `needs:`, plus a smoke test that installs the built wheel into a clean venv and runs `torsor --version`,
  `init` and `doctor`. CI runs the same wheel check, adds Python 3.13, and dogfoods the guard.

#### Fixed
- `torsor coach` no longer reports dangling `[[wikilinks]]` inside generated map notes: those are copied out of
  docstrings, not authored, and a false positive in the one detector built for precision (ADR 0010) trains people
  to ignore it. `.claude/` is excluded from the map walk.


### 💸 Token budgets that are actually enforced
- `budget.py` claimed every context-returning path was budgeted; several were not, and the ones that were
  under-counted. Fixed end to end, with a test per path (`tests/test_token_budgets.py`):
  - **The `SessionStart` digest overran its ceiling on every single session.** The Coach section was appended
    *after* every allocation was spent, and the injected header was never billed. Both are inside the budget now,
    and `bootstrap_session` truncates the assembled whole as a backstop. Measured on this repo: 515 → 448 tokens
    against a 500 ceiling.
  - **`truncate_to_tokens` appended its `…[truncated]` marker *after* the cut**, so every "budgeted" path
    overran by the marker's length. The marker is now spent from the budget.
  - **`recall` billed only the snippet** while both adapters render `### {title} ({tier})` above it — a wide
    recall overran by ~28% (1859 rendered tokens against a 1500 budget). New `budget.hit_cost` bills title and
    framing; `search.py` and `recall.py` share it.
  - **`impact` rendered every caller.** On this repo's biggest hub that was **2573 tokens in one tool call**;
    now 345. The reported `count` is still the true blast radius — the part worth paying for — and `truncated`
    says how many were withheld. New `limit` on the MCP tool and `--limit` on the CLI.
  - `get_intent` (uncapped ADR list, never truncated), `list_practices` (every detected pack at once) and
    `verify` (unbounded reasons) are now bounded by new `budgets.intent_tokens` / `practices_tokens` /
    `max_items`. `check_drift`, `check_dependencies`, `stale` and `list_commands` cap their prose output at the
    server; `check_drift(as_json=true)` stays whole, since that is the machine-readable contract.
- New `budget.cap_items(items, max_items, more=…)` returns the kept items **and an honest tail** naming how many
  were hidden. A silent truncation is more expensive than none: the agent either trusts a partial list or
  re-queries blindly. One line of tail removes both.
- Trimmed five verbose MCP tool descriptions (they sit in context for the whole session): 972 → 937 tokens.

### Fixed — two silent bugs in the polyglot map, found by review before merge
- **A JS/TS file at the repo root never resolved its own references.** A file's module key is derived from its
  path, while its importers' key is derived from the import specifier, and the two only met when the path
  contained a `/`. A flat repo therefore reported `impact = 0`, `refs = 0`, no hubs, no `connect` path and no
  Mermaid edge — silently, with a green test suite (every fixture nested its files). The ambiguity is real:
  `pkg.go` is both a plausible Python import target and a plausible root-level Go file, and no string rule
  separates them. So it is now resolved by the caller instead — `norm_path` for a file path (always strips the
  suffix), `norm_module` for a key that may be a dotted import target (keeps it). Every path-side call site was
  moved over.
- **Go's cross-file resolver was sticky, breaking ADR 0008.** It skipped edges that already had a
  `resolved_module`, and the partial-map merge reloads untouched edges from the index with their old resolution
  intact. Moving a top-level function to a sibling file in the same package left every untouched caller pointing
  at the file it had left — a *wrong* answer, not a missing one, produced automatically by the post-commit hook.
  It now re-resolves every Go edge; both branches only ever assign a target they actually found, so an edge this
  pass cannot see keeps what it had.
- `practices.py` listed JavaScript's extensions without `.cjs`, which the new `languages/` registry has — a
  `.cjs`-only repo got no best-practice pack while the map and guard saw it fine.
- The design spec's example guard scope `src/**/*.ts` does not match `src/index.ts`: `fnmatch` has no recursive
  `**`, so a leading `src/**/` demands a further `/`. Corrected to `**/*.ts`, which is what the tests already use.

## [0.7.0] — Polyglot Map (2026-09-04)

The map stops being Python-only. JavaScript, TypeScript/TSX and Go join the symbol
graph behind a new optional `[languages]` extra, and everything already built on
top of it — `impact`, `connect`, `find`, `export`, hub detection, complexity, and
`forbid_import` — widens for free because it's all built on the same `Symbol`/
`SymbolEdge` shape. Still deterministic, offline, daemon-free: one new ADR (0013,
superseding 0003), `torsor guard --strict` clean.

### 🌐 Multi-language map: JavaScript, TypeScript/TSX and Go
- `torsor-helper[languages]` is a new optional extra (`tree-sitter`, `tree-sitter-javascript`, `tree-sitter-typescript`, `tree-sitter-go` — the **official per-grammar wheels**, ~3.7 MB total, MIT, grammars compiled into the wheel) that extends the cartographer past Python. A new `languages/` registry (`LanguageSpec` per language: extensions, extractor, `requires`, optional `cross_file_resolver`/`complexity`/`imports`) replaces the old Python-only dispatch in `cartographer.py`; `languages.is_available(name)` is the single source of truth for what degrades, so a repo without the extra installed sees exactly the same Python-only map as before — byte-identical.
- **What widens for free:** because `impact`, `connect`, `find`, `export`, and Coach hub detection all consume `SymbolEdge.resolved_module` (always the canonical dotted key, whatever the source language) rather than reasoning about Python specifically, every one of them now covers JS/TS/TSX/Go the moment `[languages]` is installed — no per-feature changes needed.
- **Complexity and churn** (`torsor coach` hotspots/regressions) now score every registered language, not just `*.py` — TS/TSX modules correctly pick the TypeScript grammar rather than falling back to JS.
- **`forbid_import` guard rule** now matches JS/TS/Go import specifiers (`import`/`require`/Go import-path strings), not only Python imports — a team can write `scope: "src/**/*.ts"` rules today. `require_import` and `forbid_layer_import` stay Python-only (they reason over the `ast` module graph); that's documented, not a bug.
- **`torsor deps`** (the offline slopsquatting check) now also covers JS/TS and Go, not just Python: bare npm specifiers are checked against `package.json`'s four dependency keys, Node builtins, and `node_modules/` on disk; Go import paths are checked against `go.mod`'s `require` entries (block and single-line form), the `module` path, and a `replace` directive's left side, with a first-path-segment-has-no-dot heuristic skipping stdlib. Same conservative bias as the rest of `deps` — prefer a missed phantom over a false alarm — and degrades to a no-op on non-Python files when `[languages]` isn't installed.
- **Discoverability:** `torsor doctor` reports per-language availability (`ready` vs. "install torsor-helper[languages]"); `torsor map`'s summary line breaks module counts down by language and names any language whose files are present but *invisible* (`typescript 12 — install torsor-helper[languages]`, omitted entirely when there are no such files); a new Coach `uncharted_language` recommendation fires when non-Python source is detected but the extra isn't installed, pointing straight at the install command.
- **ADR 0013** (*Python stays on stdlib `ast`; other languages use the official tree-sitter grammar wheels, never the language pack*) supersedes ADR 0003 — 0.25+ `tree-sitter` is stable (ADR 0003's original objection no longer holds), and the official wheels are genuinely offline. `tree-sitter-language-pack` remains permanently rejected: it downloads a ~25 MB grammar bundle over the network on first use (measured 2026-09-04), which would silently break the offline guarantee. Two `forbid_import` rules enforce this: the language pack is banned everywhere under `src/`, and `tree_sitter` itself may only be imported from `languages/` so grammar access — and the degradation logic — stays in one place.
- CI gained a second axis: every matrix cell now runs the suite once with no extras (proves the degradation path, via `uv run --exact` so it's a genuinely extra-free environment) and once with `--extra languages` (proves the grammars actually work).
- **`SymbolEdge.hint` is now persisted** (`symbol_edges.hint`, **`SCHEMA_VERSION` 6 → 7**, additive `ALTER TABLE` migration — the index is disposable, so the bump costs nothing). Go's cross-file resolver branches on the hint to tell a qualified `errors.New(...)` from a bare same-package `New()`; dropping it on the SQLite round-trip made every partial map (the `auto_map_on_commit` path) re-resolve stdlib and third-party calls onto same-package symbols, inflating their ref counts.
- **The repo walk prunes during traversal.** `cartographer.iter_files` now uses `os.walk` with `dirnames` filtered in place, so it never descends into `node_modules`/`.git`/`.venv`/`vendor` at all — the old `rglob("*")` materialized and stat'd every file under those trees before discarding them (2.4x–27x slower on repos with big vendored trees). Symlinked directories are no longer followed, so a symlink cycle can't hang the walk. Same files, same path order.

### 🛡️ The edit gate: `PreToolUse` drift check on the *proposed* edit
- `torsor hooks install` now also registers a Claude Code **`PreToolUse`** hook on `Edit|Write`. Before the edit lands, `torsor hooks run pre-edit` reconstructs the **proposed file content** (a Write's `content`, or the file with the Edit's `old_string → new_string` applied), runs the ADR rules against it, ratchets against `baseline.json`, and — only when the edit would introduce *new* drift — returns the verdict with the ADR cited as `additionalContext`. Silent otherwise, so it costs nothing in the common case.
- **Advisory by default.** `automation.guard_on_edit = "advise" | "block" | "off"`; `block` denies only on new `severity: error` violations. Read-only (never touches the file), `Edit|Write` only (Bash effects aren't knowable pre-execution), ignores `.torsor/` writes. **ADR 0012.**

## [0.6.0] — Self-Serving Memory (2026-09-04)

Memory that shows up without being asked for, rules that load only where they apply,
and a garbage collector so `.torsor/` stops accumulating what nobody needs. Still
deterministic, offline, daemon-free; one new ADR (0011); `torsor guard --strict` clean.

### 🚪 Memory that arrives on its own: `SessionStart` injection (+ re-injection after `/compact`)
- `torsor hooks install` now also registers a Claude Code **`SessionStart`** hook (matcher `startup|resume|compact`) that pipes a **~500-token project digest** straight into context via `hookSpecificOutput.additionalContext` — the agent no longer has to remember to call `bootstrap_session()`, and the digest comes back **after every context compaction**, which is the documented way instructions silently vanish mid-session. Same deterministic composition as `bootstrap_session`, under a new `budgets.session_start_tokens` (default 500 — the "core tier" size the ETH Zurich instruction-file study recommends); `bootstrap_session()` stays as the fuller on-demand form. Off switch: `automation.auto_bootstrap = false`. No LLM, no daemon — one `torsor hooks run session-start` per event, exit.

### 🎯 Path-scoped rules: `torsor rules --scoped`
- Exports the standing rules as **one Claude Code rule file per ADR** under `.claude/rules/torsor/`, each with `paths:` frontmatter derived from the rule's guard `scope` — so an architecture rule enters context **only when the agent touches a file it governs**, instead of every session as one monolithic CLAUDE.md block (monolithic instruction files measurably dilute attention and add ~20% inference cost). Charter principles have no scope and become an unscoped `principles.md`. The subdirectory is fully managed (stale files removed); nothing beside it is touched. `guard.load_rules_by_note` is the single rule parser both the guard and the exporter use.

### 🔧 Build
- Pinned `mcp<2` (2.x removed `mcp.server.fastmcp`; migrating to `MCPServer` is a deliberate follow-up) and made ruff's rule set explicit (`E4,E7,E9,F`) so `uv run --with ruff ruff check` is deterministic across ruff versions. Both had CI red on a fresh resolve.

### 🧹 `torsor clean` — plan-then-apply garbage collection (+ `clean` MCP tool)
- Nothing ever removed what torsor stopped needing. `render_map` writes one note per module and **never deleted**, so renaming or deleting a source file left an orphaned map note behind — and since `map/` is committed, that orphan got pushed to git. `path_access` / `complexity_snapshot` accumulated rows for files that no longer exist, SQLite never returned freed pages, and `memory/journal/` grew one file per active day forever.
- New pure `cleaner.py` reclaims exactly four categories: **orphaned map notes**, **index rows whose source path is gone** (then `VACUUM`), **journals past `clean.journal_retention_days`** (new config, default 90; `0` disables), and — behind `--deep` — the whole disposable `.index/`.
- **Dry run by default** at both adapters: `plan()` is strictly read-only and `--apply` is the only thing that deletes. Journals are mined into `memory/insights/` *before* any are discarded, so the one non-derivable category is captured before it is dropped. Stable tiers (charter · architecture · active · insights · `commands.md` · `baseline.json` · `torsor.toml`) and source code are never touched. **ADR 0011.**
- Orphan detection mangles module names **forward** into map-note filenames rather than reverse-parsing them (`pkg/__init__.py` renders as `pkg____init__.py.md`, which reverse-parsing misreads).
- Fixed: this repo's `.torsor/.gitignore` ignored `map/`, diverging from what `torsor init` writes — the map is meant to travel with the repo, and orphan pruning is what makes that sustainable.

## [0.5.0] — Self-Driving Memory (2026-07-18)

The autonomy release: memory that captures itself on the git / agent lifecycle, so
you interact with torsor by hand almost never. Grounded in 2026 agent-memory research
(auto-capture via hooks, staleness as the top open problem, loop-engineering gates)
and kept strictly **deterministic, offline, and daemon-free** — autonomy comes from
event-driven hooks that run torsor's existing deterministic ops; torsor still never
calls an LLM. All additive over the layered core (three new ADRs; `torsor guard --strict` clean).

### 🪝 Auto-capture hooks (`torsor hooks install/uninstall/status/run` + read-only `hooks_status` MCP tool)
- One command wires **git** + **Claude Code** so memory captures itself: a **post-commit** hook auto-maps the just-committed files (reusing the partial-map merge) and refreshes the complexity snapshot; a **SessionEnd** hook writes a **deterministic auto-handoff** — a digest built from `git log/diff` since a marker + the op-log delta + new ADRs + your active-context, **no LLM** — so agents stop forgetting to call `handoff`.
- New pure `hooks.py`; marker-delimited git-hook blocks and a `.claude/settings.json` merge that are **idempotent, removable, and never clobber** your existing hooks/settings; a Husky / pre-commit detector warns instead of fighting for `.git/hooks`. Installers are **CLI-only** (footgun parity with `updater.py` — an agent shouldn't rewrite its own hooks); only the read-only `hooks_status` is an MCP tool. New `[automation]` config toggles (capture on by default; `guard_on_push` off). **ADR 0009.**

### 🧭 Staleness guard (`torsor stale` + `stale` MCP tool + Coach `dangling_link`)
- Detects memory that contradicts current code — the #1 open problem in agent memory (stale notes make agents suggest deprecated patterns). Deterministic, offline, and **high-precision by design**: dangling `[[wikilinks]]` (deletion is unambiguous — surfaced passively in the Coach) and dead file-path references restricted to inline `` `code` `` spans (real refs are backticked; example paths in prose are conventionally "double-quoted" — kept to the explicit `torsor stale` command). The `status: stale` WRITE is opt-in (`--mark`), reversible (`--unmark`), and never touches the note body. **ADR 0010.**

### ✅ Verification gate (`torsor verify` + `verify` MCP tool)
- One deterministic pass/fail gate composing guard (new drift) + deps (slopsquatting) + staleness, plus an optional recorded `test` command, into a machine-checkable verdict `{ok, exit_code, checks[], summary}` — a loop-engineering / Stop-hook / CI completion condition. Defaults to git-changed files (fast, offline); a missing `test` command reports **skip**, never fail, so the default gate stays instant static analysis. Added to the cheap-model route.

### 🕸️ Symbol-graph reach (from #7)
- **God-node (hub) detection (Coach `hub`):** high fan-in hubs over the symbol graph — the modules everything depends on.
- **`torsor connect` (+ MCP tool):** shortest directed path between two symbols over the call graph (reusing the reference edges, ADR 0007).

#### Fixed
- **Partial `map_repo` no longer wipes the index (ADR 0008):** `map_repo(paths=[…])` previously `replace_all`'d — deleting every other module's symbols/edges and inserting only the scanned subset. It now **merges** the rescanned modules into the existing graph and recomputes `refs` across the union, producing a graph byte-identical to a full remap (correctness fix; true incremental scanning remains a fast-follow).
- **Single-source tier weights:** `search.py` and `recall.py` shared duplicate `_TIER_WEIGHTS` dicts that could silently diverge indexed vs. keyword ranking; both now alias one canonical `models.TIER_WEIGHTS` (identity-pinned by a test).

## [0.4.0] — Token Thrift (2026-06-16)

### Fuzzy + frecency finder & cross-tool publishing
- **🧭 `--client` for managed blocks:** `torsor rules` / `primer` / `models --write` accept `--client <name>` to write the block into that tool's *conventional* instructions file automatically (CLAUDE.md for Claude Code/Desktop, GEMINI.md for Gemini, AGENTS.md cross-tool default) — no path needed. `clients.instructions_file()`; an explicit `--write` path still overrides.

### Token thrift — spend fewer, cheaper tokens

torsor never calls an LLM; it makes the exact, deterministic answers cheap to fetch and tells your harness how to route models. The expensive tokens in agentic coding are *re-derivation* — these three features cut it.

- **🧰 Learned command book (`torsor commands` + `record_command`/`list_commands` MCP tools):** record `test`/`build`/`lint`/`run` once into committed Markdown (`.torsor/commands.md`); surfaced in the primer so every session knows them without re-deriving. `--run <name>` replays from the repo root; the MCP server records & lists but never executes (the agent runs commands with its own shell).
- **📊 Op-frequency recipes (`torsor recipes` + `recipes` MCP tool):** the deterministic read-tools (`recall`/`get_intent`/`find_files`/`impact`/`check_drift`/`check_dependencies`/`get_rules`) record each call best-effort into a new `op_log` table (SCHEMA_VERSION 5→6, additive; never creates the index just to log, never raises); `recipes` surfaces the most-repeated lookups — the recurring exact-answer work to route to a cheap model. Frequency tracking, not a stale answer cache.
- **💸 Cheap/smart model routing (`torsor models` + `get_model_policy` MCP tool):** new `[models]` config (cheap/smart/fast); `operations.model_policy` renders a routing policy (deterministic torsor lookups + command replays → cheap model; design/code/decisions → smart model); `torsor models --write AGENTS.md` injects an idempotent "Model routing" block into the prompt file. torsor *declares* the policy; the orchestrator routes. **App-agnostic** — the policy is consumable three universal ways: the `get_model_policy(as_json?)` MCP tool (any MCP client), a Markdown block in any agent's rules file (`--write AGENTS.md`), or machine-readable JSON for any programmatic router (`torsor models --json` / `--write policy.json`).

- **🔎 Fuzzy + frecency finder (`torsor find <query>` + `find_files` MCP tool):** fast, offline navigation over the repo's files **and** torsor's mapped symbols — greedy subsequence fuzzy matching with consecutive/boundary bonuses, smart-case, and strong basename preference, plus `literal` and `regex` modes. Files rank by match quality × **frecency** (a new `path_access` table: count + a monotonic per-find recency counter, deterministic — no wall-clock; SCHEMA_VERSION 4→5, additive); symbols by a small `refs` boost. Inspired by [dmtrKovalenko/fff](https://github.com/dmtrKovalenko/fff) — adopts its fuzzy+frecency *ideas* in pure Python while keeping torsor per-call/stateless/offline (no daemon, no Rust; run fff alongside for fff-grade speed on huge repos).

## [0.3.0] — Resilience Release (2026-06-10)

Four research-driven features targeting documented vibe-coding failure modes (USENIX '25 slopsquatting; "Lost in the Middle"; GitClear duplication; CSA/Veracode security surveys; flow-debt & Truck-Factor papers), each hardened by adversarial review. All local-first, deterministic, offline-testable.

- **📦 Slopsquatting guard (`torsor deps` + `check_dependencies` MCP tool + Coach `phantom_dep`):** flags top-level imports that resolve to no known package — possible hallucinated dependencies. "Known" = stdlib + the project's own `.venv` (via dist-info `top_level.txt`/`RECORD`, incl. PEP 420 namespace packages) + first-party repo modules + declared deps (pyproject incl. PEP 735 `[dependency-groups]` + poetry groups + requirements, with a dist→import alias table). Fully offline; conservative (zero false positives across torsor's own 89 files); advisory (top-level only — submodule hallucinations aren't caught).
- **🔎 Impact analysis (`torsor impact <symbol>` + `impact()` MCP tool):** lists every caller of a symbol across files (blast radius), via the v0.2 reference edges — so the agent sees what breaks before regenerating a symbol.
- **🔗 Temporal-coupling recommendations (Coach `coupling`):** mines git history for file pairs that change together far more than chance (degree = co-changes / min(changes), skipping merge/sweep commits) and recommends documenting the hidden dependency for pairs not already linked by an import edge.
- **📉 Complexity-trend regressions (Coach `regression` + `consolidate` snapshot):** reports only files whose complexity rose meaningfully (≥5 absolute AND ≥25% relative) since the last `consolidate` snapshot — regression-since-baseline instead of absolute-badness nagging. New `complexity_snapshot` table (SCHEMA_VERSION 3→4, additive).

#### Fixed
- **`_norm_module` src-layout reconciliation:** a symbol in `src/proj/core.py` (module `src.proj.core`) and an import resolving to `proj.core` never matched, so impact analysis — and v0.2 cross-module ref counts / Mermaid — silently missed every cross-module edge on `src/`-layout repos. `_norm_module` now strips a leading `src.`/`lib.` source-root segment so both sides canonicalize equally (documented non-injective caveat for pathological duplicate-path-tail repos).
- Coupling self-edges excluded and the git-log commit parser hardened with a `#commit#` sentinel (no 40-hex-filename ambiguity).

## [0.2.0] — Intelligence Release (2026-06-02)

Twelve improvements distilled from deep competitive research (mem0/Zep/Graphiti, Aider/Serena/SCIP, CodeScene, ArchUnit/dependency-cruiser/ast-grep, Anthropic Contextual Retrieval, FlashRank/MMR, llms.txt/DeepWiki) and hardened by an adversarial review (which killed three plausible-but-wrong ideas and sharpened the rest). All dependency-free, deterministic, and offline-testable — every torsor invariant preserved.

#### 🔎 Retrieval got sharper
- **Contextual breadcrumbs** — the indexer prepends each note's structural breadcrumb (tier · path · title) to its *embedder input* and *FTS title* (the FTS body / displayed snippet stay byte-identical), so a query for situating terms finds the note (cf. Anthropic Contextual Retrieval).
- **Section-aware snippets** — recall returns the densest matching section (term frequency + heading bonus) instead of the first keyword hit. Shared by the index and keyword paths.
- **Importance decay** — `hybrid_search` scales each hit by a monotonic access-count multiplier with per-tier floors (charter/architecture never decay; episodic noise sinks to its floor until recalled). Deterministic, no schema change.
- **MMR diversification + tier-first packing + omitted marker** — near-duplicate notes are demoted via Maximal Marginal Relevance over the stored vectors (no-op when <2 vectors); ties pack toward the stabler tier; a sentinel marks budget/limit truncation.

#### 🗺️ The map gained real edges
- **AST reference edges + honest ref counts** — `cartographer.extract_edges` records resolved `(caller, name, role, module)` edges (same-module defs + `from x import y` aliases), and `Symbol.refs` is now the count of *real* references, not substring matches in comments/strings. New `symbol_edges` table, `who_references` / `module_edges` (schema v3, additive migration).
- **Repo-fingerprint skip** — `torsor map` skips the whole scan+reindex when no `*.py` file changed (`--force` overrides); cheap to keep the map fresh.
- **`torsor export`** — serializes the pyramid to a portable `llms.txt` and injects a GitHub-renderable **Mermaid** module-dependency diagram into the repo map.

#### 🛡️ Guardrails grew up (CI-ready)
- **`require_import`** (mandatory seams) and **`forbid_layer_import`** (layering: "files matching X may not import Y") rule kinds.
- **Severity + machine-readable findings** — rules carry `severity` (hint/info/warning/error) + a stable `rule_id`; `torsor guard --json` emits structured findings; `--strict --severity <level>` gates CI by threshold.
- **Drift baseline / ratchet** — `torsor guard --update-baseline` records existing debt to `.torsor/baseline.json` (committed config, keyed by `(file, rule_kind, target)` counts) so `--strict` fails only on *new* drift. Wired into the MCP `check_drift(new_only=…)` too.

#### 🧭 The Coach prioritizes
- **Churn × complexity hotspots** — `git log` churn × an AST complexity proxy surfaces the top files to refactor/test first (gracefully empty outside a git repo).
- **ADR supersedes** — `record_decision(..., supersedes=…)` flips a prior ADR to `status: superseded`; recall and `get_intent` drop superseded decisions so stale intent stops resurfacing.

#### Fixed (from the adversarial review)
- A partial `torsor map` no longer leaves a stale full-scan fingerprint that could make a later full map falsely skip on an incomplete graph.
- The budget-omitted recall marker now counts the full relevant pool (not just the limit-capped candidates) and is labelled budget/limit.

## [0.1.0] — Foundation through Coach

### Usability & docs
- **HTTP/team transport:** `torsor mcp --http [--host --port]` serves over streamable-http (shared/remote use); stdio remains the default.
- **One-command client setup:** `torsor init --write` writes/merges a project `.mcp.json` (preserving other servers) so Claude Code and other clients auto-detect torsor-helper.
- **Per-client config:** `torsor init --client <name>` prints exact setup — `claude mcp add` for Claude Code, TOML for Codex, the `mcpServers` block for Cursor/Windsurf/VS Code/Gemini/Cline/Roo/Trae/Kiro/Warp.
- **Spectacular README:** detailed install matrix (uv tool / pipx / uvx / pip / source), per-client connection guides, full CLI + MCP-tool reference, a typical-loop walkthrough, and a "what's inside" architecture map.

### Phase 5 — Consolidation
- `torsor consolidate` (+ `consolidate` MCP tool): a self-improving maintenance pass.
- Mines journal entries (`## HH:MM · kind`) into curated, deduped per-kind insight notes under `memory/insights/` (`learning`/`decision`/`rejection`/`blocker`) — idempotent, indexed, and surfaced by the Coach as `learning` recs.
- Detects duplicate journal entries and reindexes so mined insights are immediately recallable; `db.top_accessed` surfaces the most-recalled notes.
- Never deletes source Markdown — consolidation only adds derived insights and reports. HTTP/team transport and auto-pruning are deferred fast-follows.

### Phase 6 — Coach
- An independent, non-intrusive advisor surfaced via `torsor coach` and the `recommend()` MCP tool.
- Hygiene/maturity checks (deterministic): `thin` (seed-template files), `stale` (untouched active context), `unruled` (decisions without machine-readable rules), `uncharted` (source modules missing from the map).
- Best-practice recs (retrieval): `reuse` (existing symbols matching a context — anti-duplication) + relevant prior `decision`/`learning` notes.
- Dismissal + decay via a disposable `coach_state.json`; recs rank by severity and cite their source. Advisory — never blocks or edits.
- `bootstrap_session` now **pushes** a short hygiene digest (thin/stale/unruled) at session start — read-only, dismissal-aware, and silent on a healthy project (proactive delivery, not just on-demand).
- Deferred fast-follows: insight auto-mining, severity escalation over repeat checkups, and weaving recs into `bootstrap_session`/`get_intent`/`check_drift` outputs.

### Phase 4 — Guard
- ADRs carry machine-readable `rules:` in frontmatter; `record_decision()` writes numbered ADRs.
- Deterministic drift detection: `forbid_import` (stdlib `ast`) and `forbid_pattern` (regex), each citing the ADR that declared the rule.
- `check_drift()` MCP tool + `torsor guard` CLI (advisory by default; `--strict` exits non-zero for CI).
- Sampling-based semantic guard intentionally deferred to a fast-follow (client-dependent, non-deterministic).

### Phase 3 — Map
- `cartographer` extracts a symbol inventory (function/class/method, signature, line, doc) from Python source with the stdlib `ast` module.
- `map_repo()` writes a committed `map/overview.md` + `map/modules/*.md` and stores symbols in a queryable `symbols` table (schema v2).
- `get_intent()` surfaces the architecture tier (system-patterns, tech-context, ADRs) plus symbols relevant to a topic. `torsor map` CLI.
- Decision: stdlib `ast` instead of tree-sitter (unstable binding); multi-language is planned.

### Phase 2 — Index
- Derived SQLite index: FTS5 (keyword), float32-BLOB embeddings with NumPy cosine, and a wiki-link edge graph.
- Hybrid retrieval via Reciprocal Rank Fusion (vector + FTS) with tier weights, recency, and a 1-hop graph boost.
- Incremental, content-hash-based reindex that rebuilds when the embedder changes. `torsor index` CLI.
- `fastembed` is an optional extra; the default `HashingEmbedder` keeps the toolkit offline and deterministic.
- Decision: float32 BLOB + NumPy cosine instead of `sqlite-vec` (portability).

### Phase 1 — Foundation
- Pyramidal `.torsor/` Markdown wiki (charter → architecture/ADRs → map → active → episodic), git-versioned and Obsidian-readable.
- MCP server (FastMCP) with `bootstrap_session`, `recall`, `remember`, `update_active`, `handoff`.
- `torsor init` / `mcp` / `doctor` CLI; per-client MCP config snippets for 12 clients.
- Token-budgeted context everywhere; Markdown is the source of truth, the index is disposable.

### Packaging
- MIT-licensed; complete PyPI metadata (authors, classifiers, project URLs, keywords) and a lean sdist (excludes `.torsor/`, `docs/`, CI config).
- Verified: `uv build` produces a clean wheel + sdist and the `torsor` console script runs from a fresh install.
- GitHub Actions: CI (lint + tests on 3.11/3.12) and a secret-less **PyPI Trusted Publishing** release workflow. See [`PUBLISHING.md`](PUBLISHING.md).

### Fixed
- `bootstrap_session` recent-memory now spans multiple journal days (a fresh/sparse latest day no longer hides prior memory).

### Notes
- Designed and built with the brainstorm → spec → plan → TDD → review workflow; specs and plans live under [`docs/superpowers/`](docs/superpowers/).
- Phases 5 (consolidation) and 6 (the Coach — proactive recommendations) are on the roadmap. See [`docs/superpowers/specs/2026-06-01-torsor-coach-design.md`](docs/superpowers/specs/2026-06-01-torsor-coach-design.md).
