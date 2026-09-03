---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-09-03T21:10:00'
updated: '2026-09-03T21:10:00'
rules:
- kind: forbid_pattern
  target: shutil\.rmtree
  scope: src/torsor_helper/operations.py
  severity: error
  message: "recursive deletion belongs in cleaner.py (ADR 0011) — operations.py orchestrates a plan, it never removes trees itself"
---

# ADR 0011: Cleanup is plan-then-apply, and never touches a stable tier

## Context
Everything torsor writes lives under the project root, so `.torsor/` already travels with the repo and dies with it — but nothing ever removed what torsor stopped needing. `render_map` writes one note per module and never deletes, so renaming or deleting a source file left a map note behind forever; because `map/` is committed, that orphan got pushed to git. `path_access` and `complexity_snapshot` accumulate rows for files that no longer exist, SQLite never returns freed pages without a VACUUM, and `memory/journal/` grows one file per active day with no retirement path. A garbage collector is the obvious fix, but a GC that deletes the wrong thing destroys the source of truth the whole tool exists to protect.

## Decision
Cleanup is a pure `plan` followed by an explicit `apply`, both in `cleaner.py`, orchestrated by `operations.clean` and exposed as `torsor clean` / the `clean` MCP tool. `plan` is strictly read-only — the dry run is the default at both adapters, and `--apply` is the only thing that deletes. Four categories, and only four: orphaned map notes, index rows whose source path no longer exists (then VACUUM), journals past `clean.journal_retention_days` (default 90; 0 disables), and — behind `--deep` — the whole disposable `.index/`. Everything else is off limits: charter, architecture, active, insights, `commands.md`, `baseline.json`, `torsor.toml`, and any source file. Orphan detection mangles module names *forward* into map-note filenames rather than reverse-parsing them, because `pkg/__init__.py` renders as `pkg____init__.py.md` and reverse-parsing is ambiguous. Journals are mined into `memory/insights/` before any are discarded, so the only non-derivable category is captured before it is dropped. `map/` is committed (only `.index/` is git-ignored), which is what `torsor init` has always written; orphan pruning is what makes committing it sustainable.

## Consequences
`.torsor/` stops accumulating files nobody asked for, and what does get committed stays honest — a map note exists only while its module does. The dry-run default means clean can be run reflexively without reading the docs first. Costs: committed map notes churn on every `auto_map_on_commit`, so diffs carry map noise; and journal retention is the one place clean discards something a rebuild cannot recreate, which is why it is window-bounded, mines first, itemizes each file in the dry run, and can be switched off entirely. A guard rule keeps recursive deletion out of `operations.py`, so the destructive surface stays in one reviewable module.
