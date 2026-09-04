# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

torsor-helper is a persistent-memory + architectural-drift-guardrail MCP server for AI coding agents. Plain Markdown under `.torsor/` is the source of truth; a disposable SQLite index is derived from it. Python ≥ 3.11, packaged with hatchling, developed with `uv`.

## Commands

```bash
uv run --extra dev pytest -q                  # full test suite
uv run --extra dev pytest tests/test_guard_rules.py -q        # one file
uv run --extra dev pytest -k "test_name" -q                   # one test
uv run --with ruff ruff check src tests       # lint (CI runs exactly this)
uv run torsor <command>                       # run the CLI locally
```

CI (`.github/workflows/ci.yml`) runs lint + tests on Python 3.11 and 3.12. Releasing is documented in `PUBLISHING.md`. The version lives in `src/torsor_helper/__init__.py` (hatch dynamic version).

This repo dogfoods itself: `.torsor/` contains real ADRs whose layering rules `uv run torsor guard --strict` enforces against this codebase. Run it after structural changes.

## Architecture

**Layered: pure core under thin adapters.** `server.py` (FastMCP) and `cli.py` (Typer) are the only adapters, and they reach only into `operations.py` — the tested orchestration core. Core modules never import adapters. This is ADR-enforced (`.torsor/architecture/decisions/0002-…`) and `torsor guard` will flag violations. Put new logic in `operations.py` (or a core module it calls) and expose it via thin wrappers in both `server.py` and `cli.py` — nearly every feature is both an MCP tool and a CLI command. The deliberate exception is `updater.py` (`torsor self-update`): CLI-only by design, since an agent updating its own server is a footgun.

**Everything lives under the project root — nothing in `$HOME`, XDG or `/tmp`** — so `.torsor/` travels with the repo and dies with it. Only `.torsor/.index/` is git-ignored; `map/` is committed (which is why orphaned map notes must be pruned, not left to accumulate in git).

**Markdown is the source of truth; the index is throwaway.** `store.py` does all Markdown I/O (YAML frontmatter + `[[wikilinks]]`, five stability tiers: charter → architecture → map → active → memory). `indexer.py` incrementally derives the SQLite index in `db.py` (FTS5 + embedding vectors + wiki-link edges + symbols + symbol_edges; `SCHEMA_VERSION` guards migrations). Never treat the index as authoritative.

**Core module roles** (the non-obvious ones):
- `search.py` — hybrid recall: RRF fusion of FTS5 + vector results, plus importance decay and MMR diversity. `recall.py` is the keyword-only fallback when no index exists.
- `embeddings.py` — fastembed if installed (`embeddings` extra), otherwise a deterministic hashing embedder. Tests rely on the hashing fallback being offline.
- `cartographer.py` — stdlib-`ast` symbol map + reference edges ("who calls what"). Deliberately not tree-sitter (ADR 0003); reference edges resolve only the two reliable cases (ADR 0004). `impact` (who-references) and `connect` (shortest directed path between two symbols) both reuse these edges rather than building a separate call graph (ADR 0007).
- `guard.py` — ADRs carry machine-readable `rules:` blocks in frontmatter (forbid_import, layering, seams); guard checks code against them. `baseline.py` is the committed ratchet so `--strict` only fails on *new* drift. The guard is advisory — it never blocks or edits code.
- `deps.py` — advisory, offline dependency check (ADR 0006): flags phantom/slopsquatted imports against declared/installed deps. Conservative by design (prefers a missed phantom over a false alarm).
- `finder.py` — `torsor find`: fuzzy subsequence matcher over the symbol index (boundary-aware scoring), the keyword path when you don't have an exact name.
- `coach/` — hygiene/health recommendations (hotspots, temporal coupling, complexity trend, and `hubs` — high-fan-in "God node" detection over the symbol graph); a digest is pushed into `bootstrap_session` output.
- `export.py` — `torsor export` emits `llms.txt` + a Mermaid module-dependency graph from the index.
- `cleaner.py` — `torsor clean`: plan-then-apply GC over derived artefacts (orphaned map notes, index rows whose source file is gone, journals past `clean.journal_retention_days`, and `--deep` for the whole `.index/`). `plan()` is strictly read-only and the dry run is the default at both adapters; it never touches a stable tier or source code (ADR 0011). Orphan detection mangles module names *forward* into map-note filenames — never reverse-parse one, `pkg/__init__.py` renders as `pkg____init__.py.md`.
- `torsor rules --scoped` writes one path-scoped rule file per ADR to `.claude/rules/torsor/` (`paths:` derived from each rule's guard `scope` via `_scope_to_paths_glob`); that subdirectory is fully managed — never hand-edit it, edit the ADR.
- `clients.py` — registry of supported AI clients (Claude Code, Cursor, Codex, Gemini, …); the `--client` flag resolves the conventional instructions file for `rules`/`primer`/`models --write`.
- `hooks.py` — pure core for the auto-capture layer (git-hook managed blocks, `.claude/settings.json` merge). Installs `SessionStart` (matcher `startup|resume|compact` → `ops.session_start_context`, a ~500-token digest injected as `hookSpecificOutput.additionalContext`), `PreToolUse` on `Edit|Write` (→ `ops.pre_edit`: rules run against the *proposed* text, baseline-ratcheted, advisory unless `automation.guard_on_edit = "block"`; ADR 0012), `SessionEnd`/`Stop` (auto-handoff), `post-commit`, and opt-in `pre-push`. Installers are CLI-only (ADR 0009).
- `budget.py` — every context-returning path is token-budgeted; preserve this when adding output paths.
- Feature clusters that follow the same core-plus-adapter shape: `practices.py` (curated per-language best-practice packs), `deps.py` (dependency drift, venv-first with a declared-deps fallback), `models.py` (model-policy tiering), `clients.py`/`updater.py` (per-client instruction files + CLI self-update).

**Graceful degradation is a design rule:** no index → keyword recall; no fastembed → hashing embeddings; everything works offline with no API key.

## Conventions

- TDD: failing test first, then minimal implementation. Tests inject clocks via `CLOCK = lambda: datetime(...)` (ruff E731 is intentionally ignored for this).
- Ruff config in `pyproject.toml`: line length 110, target py311.
- Design specs and phase plans live in `docs/superpowers/`; architectural decisions in `.torsor/architecture/decisions/`. Record a new ADR when making a load-bearing structural choice.
- `models.py` defines the five-tier `Tier` IntEnum where `CHARTER == 0` is falsy — never test a tier with truthiness (`if note.tier:`); compare explicitly (`is`/`==`).
- `uv run torsor --help` lists the full command surface; the README is the long-form user manual.
