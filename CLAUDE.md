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

**Layered: pure core under thin adapters.** `server.py` (FastMCP) and `cli.py` (Typer) are the only adapters, and they reach only into `operations.py` — the tested orchestration core. Core modules never import adapters. This is ADR-enforced (`.torsor/architecture/decisions/0002-…`) and `torsor guard` will flag violations. Put new logic in `operations.py` (or a core module it calls) and expose it via thin wrappers in both `server.py` and `cli.py` — every feature is both an MCP tool and a CLI command.

**Markdown is the source of truth; the index is throwaway.** `store.py` does all Markdown I/O (YAML frontmatter + `[[wikilinks]]`, five stability tiers: charter → architecture → map → active → memory). `indexer.py` incrementally derives the SQLite index in `db.py` (FTS5 + embedding vectors + wiki-link edges + symbols + symbol_edges; `SCHEMA_VERSION` guards migrations). Never treat the index as authoritative.

**Core module roles** (the non-obvious ones):
- `search.py` — hybrid recall: RRF fusion of FTS5 + vector results, plus importance decay and MMR diversity. `recall.py` is the keyword-only fallback when no index exists.
- `embeddings.py` — fastembed if installed (`embeddings` extra), otherwise a deterministic hashing embedder. Tests rely on the hashing fallback being offline.
- `cartographer.py` — stdlib-`ast` symbol map + reference edges ("who calls what"). Deliberately not tree-sitter (ADR 0003); reference edges resolve only the two reliable cases (ADR 0004). `impact` reuses these edges rather than building a call graph (ADR 0007).
- `guard.py` — ADRs carry machine-readable `rules:` blocks in frontmatter (forbid_import, layering, seams); guard checks code against them. `baseline.py` is the committed ratchet so `--strict` only fails on *new* drift. The guard is advisory — it never blocks or edits code.
- `coach/` — hygiene/health recommendations (hotspots, temporal coupling, complexity trend); a digest is pushed into `bootstrap_session` output.
- `budget.py` — every context-returning path is token-budgeted; preserve this when adding output paths.

**Graceful degradation is a design rule:** no index → keyword recall; no fastembed → hashing embeddings; everything works offline with no API key.

## Conventions

- TDD: failing test first, then minimal implementation. Tests inject clocks via `CLOCK = lambda: datetime(...)` (ruff E731 is intentionally ignored for this).
- Ruff config in `pyproject.toml`: line length 110, target py311.
- Design specs and phase plans live in `docs/superpowers/`; architectural decisions in `.torsor/architecture/decisions/`. Record a new ADR when making a load-bearing structural choice.
