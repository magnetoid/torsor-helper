# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

torsor-helper is a persistent-memory + architectural-drift-guardrail MCP server for AI coding agents. Plain Markdown under `.torsor/` is the source of truth; a disposable SQLite index is derived from it. Python ≥ 3.11, packaged with hatchling, developed with `uv`.

## Commands

```bash
uv run --extra dev pytest -q                  # full test suite
uv run --extra dev pytest tests/test_guard_rules.py -q        # one file
uv run --extra dev pytest -k "test_name" -q                   # one test
uv run --extra dev ruff check src tests       # lint (pinned; CI runs exactly this)
uv run --extra dev mypy src/torsor_helper     # types (a ratchet, not --strict)
uv run --extra dev pytest -q -n auto          # the suite in parallel (~45s)
uv run torsor <command>                       # run the CLI locally
```

CI (`.github/workflows/ci.yml`) runs lint + tests on Python 3.11 and 3.12, and runs the test suite twice per matrix cell — once with no extras (proves the `[languages]` degradation path stays Python-only) and once with `--extra languages` (proves JS/TS/Go extraction actually works). Releasing is documented in `PUBLISHING.md`. The version lives in `src/torsor_helper/__init__.py` (hatch dynamic version).

This repo dogfoods itself: `.torsor/` contains real ADRs whose layering rules the guard enforces against this codebase. Run `uv run torsor guard --strict $(git ls-files "*.py")` after structural changes — **with the file list**, because the default is git-changed files and on a clean tree that is empty, so a bare run checks nothing and passes.

## Architecture

**Layered: pure core under thin adapters.** `server.py` (FastMCP) and `cli.py` (Typer) are the only adapters, and they reach only into the `operations/` package — the tested orchestration core. Core modules never import adapters. This is ADR-enforced (`.torsor/architecture/decisions/0002-…`) and `torsor guard` will flag violations. Put new logic in the right `operations/` submodule (or a core module it calls) and expose it via thin wrappers in both `server.py` and `cli.py` — nearly every feature is both an MCP tool and a CLI command. The deliberate exception is `updater.py` (`torsor update`): CLI-only by design, since an agent updating its own server is a footgun.

**Everything lives under the project root — nothing in `$HOME`, XDG or `/tmp`** — so `.torsor/` travels with the repo and dies with it. Only `.torsor/.index/` is git-ignored; `map/` is committed (which is why orphaned map notes must be pruned, not left to accumulate in git).

**Markdown is the source of truth; the index is throwaway.** `store.py` does all Markdown I/O (YAML frontmatter + `[[wikilinks]]`, five stability tiers: charter → architecture → map → active → memory). `indexer.py` incrementally derives the SQLite index in `db.py` (FTS5 + embedding vectors + wiki-link edges + symbols + symbol_edges; `SCHEMA_VERSION` guards migrations). Never treat the index as authoritative.

**Core module roles** (the non-obvious ones):
- `search.py` — hybrid recall: RRF fusion of FTS5 + vector results, plus importance decay and MMR diversity. `recall.py` is the keyword-only fallback when no index exists.
- `embeddings.py` — fastembed if installed (`embeddings` extra), otherwise a deterministic hashing embedder. Tests rely on the hashing fallback being offline.
- `cartographer.py` — walks the repo and dispatches per-file extraction through the `languages/` registry; never parses source itself. `languages/`: `modules.py` (leaf — shared module-key helpers, no registry import, to avoid a cycle; **call `norm_path` for a file path and `norm_module` only for a key that may be a dotted import target** — `pkg.go` is both a plausible Python import and a plausible root-level Go file, so the ambiguity is resolved by which function the caller picks, not by the string), `python.py` (stdlib `ast`, always available), `treesitter.py` (the only module that imports `tree_sitter`, and only inside functions, so it's importable without the extra), `javascript.py` (JS/TS/TSX via tree-sitter), `go.py` (Go via tree-sitter, with same-package/repo-package cross-file resolution). JS/TS/Go extraction lives behind the optional `[languages]` extra (official per-grammar wheels — never `tree-sitter-language-pack`, which fetches ~25 MB over the network on first use) and degrades to Python-only when it isn't installed (ADR 0013, superseding ADR 0003). `cartographer.compute_refs` runs each available language's `cross_file_resolver` over the whole graph; `SymbolEdge.resolved_module` is always the canonical dotted key regardless of source language, so `impact`/`find`/`export`/hub-detection consume one shape. Reference edges resolve only the two reliable cases (ADR 0004). `impact` (who-references) and `connect` (shortest directed path between two symbols) both reuse these edges rather than building a separate call graph (ADR 0007).
- `guard.py` — ADRs carry machine-readable `rules:` blocks in frontmatter (forbid_import, layering, seams); guard checks code against them. `forbid_import` also checks JS/TS/Go import specifiers (via `languages.import_specifiers`) when `[languages]` is installed; `require_import`/`forbid_layer_import` stay Python-only (they reason over the `ast` module graph). Rule kinds are `forbid_import`, `forbid_pattern`, `require_import`, `forbid_layer_import` and `forbid_cycle`. The first four read one file's source and live in `_CHECKERS`; **`forbid_cycle` is graph-wide**, so it is evaluated once per `guard_run` over the symbol map (`guard.check_cycles`) and no-ops without one. A rule that needs more than a single file's text belongs on that second path, not in `_CHECKERS`. A rule's `scope` is a **path-aware** glob (`guard.scope_matches`): `*` and `?` stay inside one path segment, `**` spans directories, and a pattern with no `/` matches at any depth the way a `.gitignore` pattern does. It was `fnmatch`, where `*` crossed `/` — so `src/pkg/*.py` silently governed everything below it, and `src/**/*.ts` matched nothing. Both failures are invisible, because a scope that matches nothing reports nothing. After changing a scope, feed the rule a deliberate violation and check it still fires. `baseline.py` is the committed ratchet so `--strict` only fails on *new* drift. The guard is advisory — it never blocks or edits code.
- `deps.py` — advisory, offline dependency check (ADR 0006): flags phantom/slopsquatted imports against declared/installed deps. Conservative by design (prefers a missed phantom over a false alarm).
- `finder.py` — `torsor find`: fuzzy subsequence matcher over the symbol index (boundary-aware scoring), the keyword path when you don't have an exact name.
- `coach/` — hygiene/health recommendations (hotspots, temporal coupling, complexity trend, and `hubs` — high-fan-in "God node" detection over the symbol graph); a digest is pushed into `bootstrap_session` output.
- `export.py` — `torsor export` emits `llms.txt` + a Mermaid module-dependency graph from the index.
- `cleaner.py` — `torsor clean`: plan-then-apply GC over derived artefacts (orphaned map notes, index rows whose source file is gone, journals past `clean.journal_retention_days`, and `--deep` for the whole `.index/`). `plan()` is strictly read-only and the dry run is the default at both adapters; it never touches a stable tier or source code (ADR 0011). Orphan detection mangles module names *forward* into map-note filenames — never reverse-parse one, `pkg/__init__.py` renders as `pkg____init__.py.md`.
- `torsor rules --scoped` writes one path-scoped rule file per ADR to `.claude/rules/torsor/` (`paths:` derived from each rule's guard `scope` via `_scope_to_paths_glob`); that subdirectory is fully managed — never hand-edit it, edit the ADR.
- `clients.py` — registry of supported AI clients (Claude Code, Cursor, Codex, Gemini, …); the `--client` flag resolves the conventional instructions file for `rules`/`primer`/`models --write`.
- `hooks.py` — pure core for the auto-capture layer (git-hook managed blocks, `.claude/settings.json` merge). Installs `SessionStart` (matcher `startup|resume|compact` → `ops.session_start_context`, a ~500-token digest injected as `hookSpecificOutput.additionalContext`), `PreToolUse` on `Edit|Write` (→ `ops.pre_edit`: rules run against the *proposed* text, baseline-ratcheted, advisory unless `automation.guard_on_edit = "block"`; ADR 0012), `SessionEnd`/`Stop` (auto-handoff), `post-commit`, and opt-in `pre-push`. Installers are CLI-only (ADR 0009).
- `paths.contained(root, p)` — the one containment check for any caller-supplied path. `check_drift` and `verify` are MCP tools, so their file lists can come from a prompt-injected agent; every path from outside goes through this before it is read or written.
- Non-derivable state lives in `.torsor/state/` (Coach dismissals, the auto-handoff watermark), never in `.index/`, which `clean --deep` removes wholesale. `store.state_file` migrates an older layout on read and keeps `.torsor/.gitignore` covering it.
- `torsor.toml` is strict: every config model forbids unknown keys, so a typo'd section fails loudly instead of silently keeping the default.
- Executing the project's recorded commands is CLI-only (`torsor verify --run-tests`), the same footgun rule as the hook installers — `ops.run_command` uses `shell=True` on content that travels in git.
- `operations/` is a package with a re-export façade: adapters and tests keep saying `from torsor_helper import operations as ops`, while each concern lives in its own submodule. **Submodules import siblings by full path, never the façade** (`from torsor_helper.operations.memory import ...`) — the façade is half-initialised while the package loads, and ADR 0014 machine-checks this.
- `render.py` — how one result item reads, shared by both adapters. Pure functions returning the *content* of a line; the bullet or indent stays with the adapter, because those genuinely differ. Add a formatter here rather than in `cli.py` or `server.py`, or the two drift — the Coach measured them changing together in 84% of commits while neither imports the other.
- `gitinfo.py` — the single git wrapper. Every git call goes through it; it passes `-z` and `core.quotePath=false`, which per-caller `subprocess.run` did not, so paths with spaces or non-ASCII names stopped being silently skipped.
- `tests/bench/` — a generated 5 000-note corpus and a timing harness. Performance claims come with a number from it, and it reports min *and* max because the filesystem-walking paths swing run to run. Profile before optimizing: on this codebase every predicted hot spot was wrong, and the real ones were `Path.resolve()` called per note and a quadratic wikilink lookup.
- **`db.connect` trusts the schema version stamp**, so a change to the DDL must come with a `SCHEMA_VERSION` bump or it will never reach an existing index. `INDEX_FORMAT_VERSION` (in `indexer.py`) is separate and governs re-embedding: bump it only when the breadcrumb, FTS title or embedding input changes, because it costs a full re-embed.
- `budget.py` — every context-returning path is token-budgeted, and the budget covers what actually lands in context (the truncation marker and a recall hit's title/heading are billed, not added on top). `truncate_to_tokens` for prose, `cap_items` for lists, `hit_cost` for recall hits. A capped list always reports the true total, so the agent knows it is partial: a silent truncation costs more than no cap, because it triggers a blind re-query. Knobs live in `BudgetConfig` (`intent_tokens`, `practices_tokens`, `max_items`) — never hardcode a ceiling. Preserve this when adding output paths.
- Feature clusters that follow the same core-plus-adapter shape: `practices.py` (curated per-language best-practice packs), `deps.py` (dependency drift, venv-first with a declared-deps fallback), `models.py` (model-policy tiering), `clients.py`/`updater.py` (per-client instruction files + the CLI's own `torsor update`).

**Graceful degradation is a design rule:** no index → keyword recall; no fastembed → hashing embeddings; everything works offline with no API key.

## Conventions

- TDD: failing test first, then minimal implementation. Tests inject clocks via `CLOCK = lambda: datetime(...)` (ruff E731 is intentionally ignored for this).
- Ruff config in `pyproject.toml`: line length 110, target py311.
- Design specs and phase plans live in `docs/superpowers/`; architectural decisions in `.torsor/architecture/decisions/`. Record a new ADR when making a load-bearing structural choice.
- `models.py` defines the five-tier `Tier` IntEnum where `CHARTER == 0` is falsy — never test a tier with truthiness (`if note.tier:`); compare explicitly (`is`/`==`).
- `uv run torsor --help` lists the full command surface; the README is the long-form user manual.
