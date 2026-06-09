# Changelog

All notable changes to **torsor-helper** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/); the project is pre-1.0 and ships
in numbered phases (see the [roadmap](README.md#️-roadmap)).

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
