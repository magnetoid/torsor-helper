# Changelog

All notable changes to **torsor-helper** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/); the project is pre-1.0 and ships
in numbered phases (see the [roadmap](README.md#️-roadmap)).

## [Unreleased]

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
