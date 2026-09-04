# torsor-helper — Multi-language map: JavaScript / TypeScript / Go (design)

**Goal:** Make `torsor map` — and everything that consumes the symbol table (`impact`, `connect`, `find`, `export`, the Coach's hotspots / complexity trend / hubs, and `forbid_import` guard rules) — work for **JavaScript, TypeScript (incl. TSX) and Go**, not only Python. Today every one of those features is `*.py`-only ([cartographer.py](../../../src/torsor_helper/cartographer.py) `rglob("*.py")`), so a JS/TS or Go shop installing torsor gets memory + `forbid_pattern` and nothing else. This is the single largest adoption blocker; every comparable 2026 tool (CodeGraph, GitNexus, code-review-graph, Codebase-Memory) covers 15–158 languages.

**Explicitly NOT in scope (by design):** the long tail of languages (the registry makes each one a small follow-up PR: one grammar wheel + one query file); type-aware receiver resolution (`this.x()` / `s.Get()` to a concrete class) — ADR 0004's "only the reliable cases" rule holds; tsconfig `paths` aliases and monorepo workspace resolution; truly incremental mapping (B2) and test-coverage edges (B3); a daemon or file watcher (ADR 0009).

## Invariants (unchanged, and load-bearing here)

- **Offline, always.** The new dependency is an *optional extra* (`torsor-helper[languages]`) made of the **official per-grammar wheels** (`tree-sitter`, `tree-sitter-javascript`, `tree-sitter-typescript`, `tree-sitter-go` — MIT, ~3.7 MB total, grammars compiled into the wheel). **Not** `tree-sitter-language-pack`: verified 2026-09-04 that it downloads a ~25 MB grammar bundle over the network on first `get_language()` call, which would silently break torsor's offline guarantee. A guard rule forbids importing it anywhere under `src/`.
- **Graceful degradation.** Without the extra, behaviour is byte-identical to today: non-Python files are skipped, Python keeps using stdlib `ast` (ADR 0003 stays true for Python). `torsor doctor` and a Coach recommendation say what's missing and how to install it.
- **Deterministic.** Symbols, edges and refs are a pure function of the source files. No runtime code generation, no per-machine state.
- **Adapters untouched.** No new MCP tool or CLI command — the existing surface just starts returning JS/TS/Go results. Core-only change (ADR 0002).

## Architecture

### New package `src/torsor_helper/languages/`

| Module | Role |
|---|---|
| `__init__.py` | The **registry**: `LANGUAGES: dict[str, LanguageSpec]` keyed by language name, each with `extensions`, an `extractor` (`(source, module) -> (symbols, edges)`), an optional `cross_file_resolver`, and `requires` (the grammar module it needs). `extractor_for(path) -> Extractor | None`, `source_extensions() -> tuple[str, ...]` (only languages whose grammar imports succeed), `available() -> dict[name, bool]`. |
| `python.py` | The existing stdlib-`ast` extractor, moved verbatim from `cartographer.py` (`extract_symbols`, `extract_edges`, `_import_aliases`, `absolute_from_module`, `_owners`). `cartographer` re-exports them so no import path changes. |
| `treesitter.py` | The shared runner: lazy `Language`/`Parser` construction per grammar (cached per process), `captures(lang, source_bytes, query) -> dict[capture, list[Node]]`, a `leading_comment(node)` helper for docstrings, and `param_text(node)` for signatures. Imports `tree_sitter` **inside** functions so the module is importable without the extra. |
| `javascript.py` | JS + TS + TSX (one extractor, three grammars — `language()`, `language_typescript()`, `language_tsx()`), queries below, and relative-import resolution. |
| `go.py` | Go extractor, queries below, and same-package + `go.mod`-prefixed import resolution. |

### What changes in `cartographer.py`

- `iter_source_files` collects `languages.source_extensions()` instead of `*.py` (so the fingerprint, hotspots, trend, health and hubs all widen automatically). `DEFAULT_IGNORE` grows `.next`, `coverage`, `vendor`, `target`, `.turbo`.
- `_scan` dispatches on suffix via `languages.extractor_for(file)`; files with no extractor are skipped (today's behaviour for non-Python).
- `norm_module` strips any registered suffix (not only `.py`) and treats `pkg/index.{js,jsx,ts,tsx,mjs}` as `pkg` — the module key an `import './pkg'` resolves to. `src.`/`lib.` stripping stays.
- `compute_refs` first runs each language's `cross_file_resolver(symbols, edges)` (idempotent; a no-op for Python and JS/TS). It's the one place both the full scan and the partial-map merge (ADR 0008) already pass the whole `(symbols, edges)` union through, so cross-file resolution stays correct in both paths without a second call site.
- `Symbol.kind` gains `"type"` (Go `type`, TS `interface` / `type` alias). `Symbol` and `SymbolEdge` gain no other fields; the DB schema is unchanged (no `SCHEMA_VERSION` bump).

### Extraction rules (what each language yields)

Signature = `name(<parameter list text>)`; doc = first line of the immediately preceding comment (JSDoc/`//`), same as Python's first docstring line. Methods are named `Owner.method` so the existing "methods score 0 refs" rule (ADR 0004) applies unchanged.

**JavaScript / TypeScript / TSX** — verified query shapes (spike, tree-sitter 0.26):

| Capture | Query | → |
|---|---|---|
| function | `(function_declaration name: (identifier) @d)` | `function` |
| arrow/const fn | `(lexical_declaration (variable_declarator name: (identifier) @d value: [(arrow_function) (function_expression)]))` | `function` |
| class | `(class_declaration name: [(identifier) (type_identifier)] @d)` | `class` |
| method | `(method_definition name: (property_identifier) @d)` (owner = enclosing class) | `method` |
| interface / type alias (TS) | `(interface_declaration name: (type_identifier) @d)`, `(type_alias_declaration name: (type_identifier) @d)` | `type` |
| call | `(call_expression function: (identifier) @r)` | edge `call` |
| `new X()` | `(new_expression constructor: (identifier) @r)` | edge `call` |
| `extends X` | `(class_heritage (identifier) @r)` | edge `read` |
| import | `(import_statement (import_clause …) source: (string) @src)` — default, named and namespace clauses | alias table |

Reference resolution (the two reliable cases, mirroring Python's): (1) a name defined at top level in the same file → that file; (2) a name bound by `import … from './rel'` or `'../rel'` → the module key of the relative target (suffix-stripped, `index.*` collapsed). Bare specifiers (`react`, `@scope/pkg`) and alias paths (`@/x`) → `resolved_module=None`. `export default function` and `module.exports = { run }` need no special casing — the *definitions* are what matter; CommonJS `require('./x')` bound via `const x = require(…)` is resolved as an alias, matching the import case.

**Go** — verified query shapes:

| Capture | Query | → |
|---|---|---|
| function | `(function_declaration name: (identifier) @d)` | `function` |
| method | `(method_declaration receiver: (parameter_list (parameter_declaration type: [(pointer_type (type_identifier) @recv) (type_identifier) @recv])) name: (field_identifier) @d)` → `Recv.Method` | `method` |
| type | `(type_declaration (type_spec name: (type_identifier) @d))` | `type` |
| call | `(call_expression function: (identifier) @r)` | edge `call` |
| qualified call | `(call_expression function: (selector_expression operand: (identifier) @pkg field: (field_identifier) @r))` | edge `call`, resolved via imports |
| import | `(import_spec path: (interpreted_string_literal) @src)` | alias table |

Resolution: (1) same file top-level; (2) **same package** — Go's normal case is calling a function defined in *another file of the same directory*, which is why `go.py` has a `cross_file_resolver`: for every unresolved `call` edge whose name is a top-level symbol in another file of the same directory, set `resolved_module` to that file; (3) `pkg.Fn` where the import path starts with the `go.mod` `module` path → the repo-relative directory (`example.com/app/util` → `util`), resolved to the file in that directory defining `Fn` by the same cross-file pass. Standard library and third-party imports → `None`.

### Consumers that widen for free, and the two that need a line

- **For free:** `map`, `impact`, `connect`, `find`, `export` (llms.txt + Mermaid), `hubs`, health's "uncharted" check, `stale` path refs, the scoped-rules exporter — all read the symbol table or `iter_source_files`.
- **Complexity** (`coach/trend.py`, `coach/hotspots.py`): today an `ast`-based branch count. Add `languages.complexity(path, source) -> int`: Python keeps the `ast` proxy; JS/TS/Go count branch nodes via one small query per grammar (`if_statement`, `for_statement`, `for_in_statement`, `while_statement`, `switch_case`, `catch_clause`, `conditional_expression`, `&&`/`||` binary expressions; Go adds `select`/`case`). Same scale, same "regressions only" semantics.
- **`forbid_import` guard rule** (`guard.py`): today `ast`-based, so it silently no-ops on non-Python files. For JS/TS/Go it matches the rule's `target` as a prefix of the import *specifier string* (`"lodash"`, `"../internal/db"`, `"example.com/app/internal"`), via the same import query. Rules keep their `scope:` glob so a team writes `scope: "src/**/*.ts"`. `require_import` and `forbid_layer_import` stay Python-only in this phase (documented).

### Degradation & discoverability

- `languages.available()` is the single source of truth. `torsor doctor` prints one line per language: `typescript: ready` / `go: install torsor-helper[languages]`.
- New Coach check `uncharted_language` (index-free, deterministic): when `practices.detect_languages` finds ≥ N source files of a language whose extractor is unavailable, recommend installing the extra — severity `info`, dismissible like every other rec.
- `torsor map` prints `(python 128 · typescript 0 — install torsor-helper[languages])` in its summary so the gap is visible where it matters.

### Phase 2 (same plan, separable): `deps` for JS/TS and Go

`deps.py` gains two small resolvers behind the same `unknown_imports(root, files)` API: **JS/TS** — bare specifiers (first segment, or first two for `@scope/pkg`) checked against `package.json` `dependencies`/`devDependencies`/`peerDependencies`, Node built-ins (`node:*` and the stdlib list), and `node_modules/<pkg>` on disk (installed-first, like the venv-first Python path); **Go** — import paths checked against `go.mod` `require` prefixes, the `module` path itself, and the stdlib heuristic (no `.` in the first path segment). Same conservative bias (ADR 0006): prefer a missed phantom over a false alarm.

## ADR 0013 (supersedes 0003)

*"Python stays on stdlib `ast`; JS/TS/Go use the official tree-sitter grammar wheels as an optional extra — never the language pack, never a download at runtime."* Rules: `forbid_import` `tree_sitter_language_pack` (scope `src/**`, severity `error`); `forbid_import` `tree_sitter` with scope `src/torsor_helper/cartographer.py` and `src/torsor_helper/operations.py` (grammar access only through `languages/treesitter.py`, so degradation logic lives in one place).

## Packaging & CI

- `pyproject.toml`: `languages = ["tree-sitter>=0.25", "tree-sitter-javascript>=0.23", "tree-sitter-typescript>=0.23", "tree-sitter-go>=0.23"]`. README install line: `uv tool install "torsor-helper[languages]"`.
- CI matrix gains an axis: the existing job (no extra — proves degradation) plus one with `--extra languages`. Language tests use `pytest.importorskip("tree_sitter")`; degradation tests monkeypatch `languages.available()` to all-False and assert Python-only output is unchanged.
- Version → 0.7.0.

## Tests (offline, deterministic)

- Per language: fixture repo (3–4 files) → exact expected symbols (name/kind/signature/line/doc) and edges (resolved and unresolved), including: TS class + method + interface; arrow-function export; `import { x } from './a'` resolving to `a`; `import './pkg'` resolving to `pkg/index.ts`; bare `react` unresolved; Go method with pointer receiver named `Store.Get`; same-package cross-file call resolved; `go.mod`-prefixed import resolved to a directory; stdlib `fmt.Println` unresolved.
- `compute_refs` over a mixed Python + TS + Go repo: refs counted per language, methods 0.
- `impact` / `connect` end-to-end on a TS fixture; `find` returns TS symbols; `export` Mermaid includes a TS module edge.
- `forbid_import` on a `.ts` file with `scope: "**/*.ts"`; on the same file without the extra → no violation and no error.
- Complexity: a TS file with 4 branches scores 4; a regression is reported after a snapshot.
- Degradation: with `available()` forced False, `iter_source_files` returns only `*.py`, `map_repo` output equals the pre-change fixture, `doctor` prints the install hint.
- Guard: `torsor guard --strict` clean on this repo with ADR 0013 in place (the `tree_sitter` import-scope rule bites immediately if grammar access leaks out of `languages/`).

## Sequencing

1. Registry + Python extractor move (pure refactor, all 444 tests still green, no behaviour change).
2. `treesitter.py` + JS/TS extractor + tests → `map`/`impact`/`find` work on a TS fixture.
3. Go extractor + cross-file resolver + tests.
4. Complexity + `forbid_import` widening; `doctor` / Coach discoverability; docs; ADR 0013; CI axis; 0.7.0.
5. Phase 2 (`deps`).
