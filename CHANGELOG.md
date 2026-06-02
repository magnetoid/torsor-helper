# Changelog

All notable changes to **torsor-helper** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/); the project is pre-1.0 and ships
in numbered phases (see the [roadmap](README.md#️-roadmap)).

## [Unreleased]

### Phase 6 — Coach
- An independent, non-intrusive advisor surfaced via `torsor coach` and the `recommend()` MCP tool.
- Hygiene/maturity checks (deterministic): `thin` (seed-template files), `stale` (untouched active context), `unruled` (decisions without machine-readable rules), `uncharted` (source modules missing from the map).
- Best-practice recs (retrieval): `reuse` (existing symbols matching a context — anti-duplication) + relevant prior `decision`/`learning` notes.
- Dismissal + decay via a disposable `coach_state.json`; recs rank by severity and cite their source. Advisory — never blocks or edits.
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

### Fixed
- `bootstrap_session` recent-memory now spans multiple journal days (a fresh/sparse latest day no longer hides prior memory).

### Notes
- Designed and built with the brainstorm → spec → plan → TDD → review workflow; specs and plans live under [`docs/superpowers/`](docs/superpowers/).
- Phases 5 (consolidation) and 6 (the Coach — proactive recommendations) are on the roadmap. See [`docs/superpowers/specs/2026-06-01-torsor-coach-design.md`](docs/superpowers/specs/2026-06-01-torsor-coach-design.md).
