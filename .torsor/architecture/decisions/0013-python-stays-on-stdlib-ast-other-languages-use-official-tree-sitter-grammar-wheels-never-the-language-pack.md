---
type: decision
status: accepted
tags:
- adr
links:
- 0003-use-stdlib-ast-for-the-cartographer-not-tree-sitter
- 0004-reference-edges-resolve-only-the-two-reliable-cases
- 0007-reuse-reference-edges-for-impact-not-a-new-call-graph
created: '2026-09-04T15:00:00'
updated: '2026-09-04T15:00:00'
supersedes: 0003-use-stdlib-ast-for-the-cartographer-not-tree-sitter
rules:
- kind: forbid_import
  target: tree_sitter_language_pack
  scope: src/**
  severity: error
  message: "the language pack downloads grammars at runtime — torsor is offline-first (ADR 0013); use the official per-grammar wheels"
- kind: forbid_import
  target: tree_sitter
  scope: src/torsor_helper/[!l]*.py
  severity: error
  message: "tree_sitter is reached only through languages/treesitter.py (ADR 0013) so degradation lives in one place"
- kind: forbid_import
  target: tree_sitter
  scope: src/torsor_helper/languages/[!t]*.py
  severity: error
  message: "treesitter.py is the only module inside languages/ allowed to import tree_sitter (ADR 0013) — an extractor that imports it directly hard-breaks the no-extra path"
---

# ADR 0013: Python stays on stdlib ast; other languages use the official tree-sitter grammar wheels, never the language pack

## Context
ADR 0003 rejected tree-sitter for the cartographer because `tree-sitter-language-pack`'s binding was unstable and incompatible with the rest of the toolchain at the time. That objection no longer holds: `tree-sitter` 0.25+ is a stable, well-maintained binding, and the official per-grammar wheels (`tree-sitter-javascript`, `tree-sitter-typescript`, `tree-sitter-go`) ship their grammar compiled directly into the wheel — MIT-licensed, ~3.7 MB total, fully offline. `tree-sitter-language-pack` is a different thing: verified 2026-09-04 that it downloads a ~25 MB grammar bundle over the network on first `get_language()` call. torsor is offline-first with no daemon and no API key; a dependency that silently reaches out to the network on first use would break that guarantee invisibly, so the language pack is rejected on the same grounds ADR 0006 rejected an online-dependency check.

Python itself never needed this debate — stdlib `ast` is zero-dependency, exact, and has no equivalent instability risk, so it stays exactly as ADR 0003 left it.

## Decision
Multi-language symbol extraction goes through a `languages/` registry (`LanguageSpec` per language: extensions, extractor, optional `requires`, `cross_file_resolver`, `complexity`, `imports`), not a hardcoded dispatch in `cartographer.py`. Python's extractor (`languages/python.py`) uses stdlib `ast`, imported unconditionally — no change from ADR 0003. JavaScript/TypeScript/TSX and Go (`languages/javascript.py`, `languages/go.py`) use the **official per-grammar tree-sitter wheels**, published as the optional `[languages]` extra (`tree-sitter>=0.25`, `tree-sitter-javascript>=0.23`, `tree-sitter-typescript>=0.23`, `tree-sitter-go>=0.23`). `tree_sitter` itself is imported from exactly one place, `languages/treesitter.py` — the shared `Parser`/`Language` runner — and only inside functions, so the module (and everything that depends on it) stays importable with the extra absent. `languages.is_available(name)` probes each spec's `requires` with a try/import and is the single source of truth for what degrades: `source_extensions()`, `spec_for()`, and `import_specifiers()` all filter through it, so a repo with `[languages]` uninstalled sees a Python-only map — not an error.

The language pack is never an option: a `forbid_import` rule bans `tree_sitter_language_pack` anywhere under `src/`. A second rule bans importing `tree_sitter` outside `languages/` (the glob `src/torsor_helper/[!l]*.py` matches every top-level module whose name doesn't start with `l` — `cartographer.py`, `guard.py`, `coach/*.py`, etc. — while exempting `languages/` itself, since fnmatch's `*` matches `/`), so grammar access can never leak into a module that assumes it's always available. A third rule closes the remaining gap *inside* `languages/`: `src/torsor_helper/languages/[!t]*.py` bans `tree_sitter` in every module there except `treesitter.py` itself, so an extractor can't hard-import a grammar at module scope and break the no-extra path.

## Consequences
Without `[languages]` installed, behaviour is byte-identical to before this feature: Python `ast` extraction, Python-only `map`/`impact`/`connect`/`find`/`export`/hub detection, `forbid_import`/`forbid_layer_import` checked only against Python imports. With it installed, all of those widen for free to JS/TS/TSX/Go, because they're built on `compute_refs`'s edges and `languages.spec_for()`'s dispatch rather than a Python-specific path. Adding a new language going forward is one wheel + one query/extractor module + one `LanguageSpec` entry — not a new subsystem. Cost: CI must run twice (with and without the extra) to prove degradation actually holds, since a regression that hard-imports `tree_sitter` at module scope would only show up in the no-extras job; `require_import` and `forbid_layer_import` remain Python-only rule kinds (they reason about the `ast` module graph) until a future ADR extends them.

Two accepted imprecisions come with going polyglot. First, canonical module keys can now **collide across languages** — `api/client.py` and `api/client.ts` both normalize to `api.client`, so their symbols share a namespace in `impact`/`connect`/`export`; this extends ADR 0004's non-injectivity caveat (duplicate path-tails) rather than introducing a new class of error, and the same conservative reading applies: a key names a *place*, not a guaranteed-unique file. Second, ES `export … from` **re-exports are not captured** by `forbid_import` or `deps` — a module that re-exports a forbidden or phantom package is not flagged through the re-exporting file, only at the original import site. That's a false negative, which is the safe direction for an advisory checker.
