# Multi-language Map (JS / TS / Go) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `torsor map` and every consumer of the symbol table (impact, connect, find, export, hubs, hotspots, complexity trend, `forbid_import`) work for JavaScript, TypeScript/TSX and Go, behind an optional `[languages]` extra, with byte-identical Python-only behaviour when the extra is absent.

**Architecture:** A new `languages/` package holds a registry (`LanguageSpec` per language) and one extractor per language, all producing the existing `Symbol`/`SymbolEdge` shapes. Python keeps stdlib `ast` (moved, not rewritten). JS/TS/Go use the official tree-sitter grammar wheels through one shared `treesitter.py` runner that imports `tree_sitter` lazily. `cartographer.py` dispatches by suffix and runs per-language cross-file resolvers inside `compute_refs`, so the full scan and the partial-map merge stay correct with one call site.

**Tech Stack:** Python 3.11+, `tree-sitter>=0.25`, `tree-sitter-javascript>=0.23`, `tree-sitter-typescript>=0.23`, `tree-sitter-go>=0.23` (all optional), pytest, uv.

**Spec:** `docs/superpowers/specs/2026-09-04-torsor-multi-language-map-design.md`

## Global Constraints

- **Offline always.** Never import or depend on `tree-sitter-language-pack` (it downloads grammars at runtime). Only the official per-grammar wheels.
- **Graceful degradation.** Without the extra, `iter_source_files` yields only `*.py` and every output is identical to today. Language tests use `pytest.importorskip("tree_sitter")`; degradation tests monkeypatch `languages.is_available` to return `False`.
- **Deterministic:** no wall-clock, no network, no per-machine state.
- **ADR 0002:** core-only change. No new MCP tool or CLI command. `tree_sitter` is imported only inside `languages/treesitter.py` (ADR 0013 rule).
- **Model changes:** `Symbol.kind` may now be `"type"`; `SymbolEdge` gains a non-persisted `hint: str | None = None`. No `SCHEMA_VERSION` bump.
- Ruff: line length 110, target py311, rule set `E4,E7,E9,F`. Run `uv run --with ruff ruff check src tests` before each commit.
- Every commit: `uv run --extra dev --extra languages pytest -q` green **and** `uv run --extra dev pytest -q` green (proves degradation), `uv run torsor guard --strict` clean.
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## File Structure

| File | Responsibility |
|---|---|
| `src/torsor_helper/languages/__init__.py` | Registry: `LanguageSpec`, `LANGUAGES`, `is_available`, `available`, `source_extensions`, `spec_for`, `extractor_for`, `complexity`, `import_specifiers` |
| `src/torsor_helper/languages/modules.py` | Leaf helpers with no torsor imports: `SOURCE_SUFFIXES`, `strip_suffix`, `norm_module` (moved from cartographer) |
| `src/torsor_helper/languages/python.py` | The stdlib-`ast` extractor moved verbatim from `cartographer.py` + `complexity(text)` |
| `src/torsor_helper/languages/treesitter.py` | Lazy grammar loading, `parse`, `captures`, `matches`, `leading_comment`, `line` — the only file that imports `tree_sitter` |
| `src/torsor_helper/languages/javascript.py` | JS/TS/TSX extractor: symbols, edges, relative-import resolution, `imports`, `complexity` |
| `src/torsor_helper/languages/go.py` | Go extractor: symbols, edges, `resolve_cross_file`, `imports`, `complexity` |
| `src/torsor_helper/cartographer.py` | Dispatch by suffix; re-exports `norm_module`, `extract_symbols`, `extract_edges`, `absolute_from_module` for back-compat |
| `src/torsor_helper/coach/hotspots.py`, `coach/coupling.py`, `coach/health.py` | Widen churn filters; complexity via registry; `check_uncharted_language` |
| `src/torsor_helper/guard.py` | `forbid_import` on non-Python via `languages.import_specifiers` |
| `src/torsor_helper/deps.py` | Phase 2: JS/TS and Go phantom-import resolvers |
| `src/torsor_helper/cli.py`, `operations.py` | `doctor` language lines; `map` per-language summary |

---

### Task 1: Registry + Python extractor move (pure refactor)

**Files:**
- Create: `src/torsor_helper/languages/__init__.py`, `src/torsor_helper/languages/modules.py`, `src/torsor_helper/languages/python.py`
- Modify: `src/torsor_helper/cartographer.py` (remove `extract_symbols`, `extract_edges`, `_import_aliases`, `_owners`, `absolute_from_module`, `norm_module`; import them from `languages`)
- Test: `tests/test_languages_registry.py`

**Interfaces:**
- Produces: `languages.LanguageSpec(name, extensions, extractor, requires=(), cross_file_resolver=None, complexity=None, imports=None)`; `languages.LANGUAGES: dict[str, LanguageSpec]`; `languages.is_available(name) -> bool`; `languages.available() -> dict[str, bool]`; `languages.source_extensions() -> tuple[str, ...]`; `languages.spec_for(path) -> LanguageSpec | None`; `languages.extractor_for(path)`; `languages.modules.norm_module(module) -> str`; `languages.python.extract(source, module) -> tuple[list[Symbol], list[SymbolEdge]]`.

- [ ] **Step 1: Write the failing registry test**

```python
# tests/test_languages_registry.py
from torsor_helper import languages
from torsor_helper.languages.modules import norm_module


def test_python_is_always_available_and_first():
    assert languages.is_available("python") is True
    assert ".py" in languages.source_extensions()


def test_spec_for_dispatches_on_suffix():
    assert languages.spec_for("pkg/x.py").name == "python"
    assert languages.spec_for("pkg/x.txt") is None


def test_python_extractor_is_the_registry_entry(tmp_path):
    symbols, edges = languages.extractor_for("a.py")("def f():\n    return g()\n", "a.py")
    assert [s.name for s in symbols] == ["f"]
    assert any(e.referenced_name == "g" and e.caller == "f" for e in edges)


def test_unavailable_language_is_skipped(monkeypatch):
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")
    assert languages.source_extensions() == (".py",)
    assert languages.spec_for("x.ts") is None


def test_norm_module_still_canonicalizes_python():
    assert norm_module("src/pkg/mod.py") == "pkg.mod"
    assert norm_module("pkg/dates.py") == "pkg.dates"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --extra dev pytest tests/test_languages_registry.py -q`
Expected: `ModuleNotFoundError: No module named 'torsor_helper.languages'`

- [ ] **Step 3: Create `languages/modules.py` (leaf, no torsor imports)**

```python
# src/torsor_helper/languages/modules.py
from __future__ import annotations

# Every suffix any registered language claims. Kept here (a leaf module) so
# norm_module can strip them without importing the registry — which would be
# circular, since the registry imports the extractors that call norm_module.
SOURCE_SUFFIXES = (".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go")


def strip_suffix(module: str) -> str:
    for suffix in SOURCE_SUFFIXES:
        if module.endswith(suffix):
            return module[: -len(suffix)]
    return module


def norm_module(module: str) -> str:
    """Normalize a module key to dotted form so a file relpath ("pkg/dates.py")
    and an import target ("pkg.dates") compare equal. Strips a leading source-root
    segment ("src/", "lib/") so a src-layout file canonicalizes to its import
    name. JS/TS `pkg/index.ts` collapses to `pkg` — the key `import './pkg'`
    resolves to. Not injective across duplicate path-tails (see ADR 0004)."""
    stripped = strip_suffix(module)
    if stripped.endswith("/index") and not module.endswith(".py"):
        stripped = stripped[: -len("/index")]
    dotted = stripped.replace("/", ".")
    for root in ("src.", "lib."):
        if dotted.startswith(root):
            return dotted[len(root):]
    return dotted
```

- [ ] **Step 4: Create `languages/python.py` by moving the ast code**

Move these from `cartographer.py` **verbatim** (cut, don't copy): `_signature`, `_first_line`, `extract_symbols`, `absolute_from_module`, `_import_aliases`, `_owners`, `extract_edges`. Replace `norm_module` uses with `from torsor_helper.languages.modules import norm_module`. Then append:

```python
# src/torsor_helper/languages/python.py  (bottom)
def extract(source: str, module: str) -> tuple[list[Symbol], list[SymbolEdge]]:
    return extract_symbols(source, module), extract_edges(source, module)


# Branch-y nodes used as a cheap complexity proxy (file-grained; pairs with git
# churn in the Coach). Moved from coach/hotspots so every language has one.
_DECISION_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.BoolOp)


def complexity(text: str) -> int:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return 0
    return text.count("\n") + 1 + sum(isinstance(n, _DECISION_NODES) for n in ast.walk(tree))
```

- [ ] **Step 5: Create the registry**

```python
# src/torsor_helper/languages/__init__.py
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import Callable

from torsor_helper.languages import python as _py
from torsor_helper.models import Symbol, SymbolEdge

Extractor = Callable[[str, str], tuple[list[Symbol], list[SymbolEdge]]]
Resolver = Callable[[list[Symbol], list[SymbolEdge]], None]


@dataclass(frozen=True)
class LanguageSpec:
    name: str
    extensions: tuple[str, ...]
    extractor: Extractor
    requires: tuple[str, ...] = ()               # importable modules the extractor needs
    cross_file_resolver: Resolver | None = None  # run inside compute_refs over the whole graph
    complexity: Callable[[str], int] | None = None
    imports: Callable[[str], list[tuple[str, int]]] | None = None  # (specifier, line) for guard/deps


LANGUAGES: dict[str, LanguageSpec] = {
    "python": LanguageSpec("python", (".py",), _py.extract, complexity=_py.complexity),
}


@lru_cache(maxsize=None)
def is_available(name: str) -> bool:
    """True when every module the language's extractor needs imports cleanly.
    Python always; the tree-sitter languages only with the [languages] extra."""
    for mod in LANGUAGES[name].requires:
        try:
            import_module(mod)
        except ImportError:
            return False
    return True


def available() -> dict[str, bool]:
    return {name: is_available(name) for name in LANGUAGES}


def source_extensions() -> tuple[str, ...]:
    out: list[str] = []
    for spec in LANGUAGES.values():
        if is_available(spec.name):
            out.extend(spec.extensions)
    return tuple(out)


def spec_for(path) -> LanguageSpec | None:
    suffix = Path(path).suffix
    for spec in LANGUAGES.values():
        if suffix in spec.extensions and is_available(spec.name):
            return spec
    return None


def extractor_for(path) -> Extractor | None:
    spec = spec_for(path)
    return spec.extractor if spec else None


def complexity(path: Path) -> int:
    """File-grained complexity proxy for any registered language; 0 when the
    file is unreadable or its language isn't available."""
    spec = spec_for(path)
    if spec is None or spec.complexity is None:
        return 0
    try:
        return spec.complexity(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError):
        return 0


def import_specifiers(relpath: str, text: str) -> list[tuple[str, int]]:
    """(import specifier, line) pairs for a non-Python file; [] when unknown."""
    spec = spec_for(relpath)
    if spec is None or spec.imports is None:
        return []
    return spec.imports(text)
```

- [ ] **Step 6: Rewire `cartographer.py`**

Delete the moved functions and add at the top:

```python
from torsor_helper import languages
from torsor_helper.languages.modules import norm_module
from torsor_helper.languages.python import absolute_from_module, extract_edges, extract_symbols  # noqa: F401  (back-compat re-exports)

_norm_module = norm_module  # back-compat alias
```

In `_scan`, replace the two `extend` lines with dispatch (identical behaviour for `.py` today):

```python
        extractor = languages.extractor_for(file)
        if extractor is None:
            continue
        syms, eds = extractor(src, module)
        symbols.extend(syms)
        edges.extend(eds)
```

In `iter_source_files`, replace `root.rglob("*.py")` with a suffix filter over `languages.source_extensions()`:

```python
def iter_source_files(root: Path, ignore: set[str] = DEFAULT_IGNORE) -> list[Path]:
    root = Path(root)
    exts = set(languages.source_extensions())
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in exts or not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in ignore for part in rel_parts):
            continue
        out.append(path)
    return out
```

Update `repo_fingerprint`'s docstring from "*.py files" to "source files". `guard.py` imports `absolute_from_module` from `cartographer` — unchanged thanks to the re-export.

- [ ] **Step 7: Run the whole suite**

Run: `uv run --extra dev pytest -q && uv run --with ruff ruff check src tests && uv run torsor guard --strict`
Expected: 444 + 5 passed; lint clean; no drift.

- [ ] **Step 8: Commit**

```bash
git add src/torsor_helper/languages src/torsor_helper/cartographer.py tests/test_languages_registry.py
git commit -m "refactor(languages): registry + move the Python extractor out of cartographer

Pure refactor: cartographer dispatches by suffix through a LanguageSpec
registry; Python's stdlib-ast extractor moves to languages/python.py and
norm_module to the leaf languages/modules.py. No behaviour change.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: tree-sitter runner + JS/TS symbols

**Files:**
- Create: `src/torsor_helper/languages/treesitter.py`, `src/torsor_helper/languages/javascript.py`
- Modify: `pyproject.toml` (extra), `src/torsor_helper/languages/__init__.py` (register)
- Test: `tests/test_lang_javascript.py`

**Interfaces:**
- Produces: `treesitter.grammar(name) -> Language` for `"javascript" | "typescript" | "tsx" | "go"`; `treesitter.parse(name, text) -> Tree`; `treesitter.captures(name, root, query) -> dict[str, list[Node]]`; `treesitter.matches(name, root, query) -> list[dict[str, list[Node]]]`; `treesitter.leading_comment(node) -> str`; `treesitter.text(node) -> str`; `treesitter.line(node) -> int`. `javascript.extract(source, module)` (symbols only in this task; edges in Task 3).

- [ ] **Step 1: Add the extra**

In `pyproject.toml` under `[project.optional-dependencies]`:

```toml
languages = [
    "tree-sitter>=0.25",
    "tree-sitter-javascript>=0.23",
    "tree-sitter-typescript>=0.23",
    "tree-sitter-go>=0.23",
]
```

- [ ] **Step 2: Write the failing symbol tests**

```python
# tests/test_lang_javascript.py
import pytest

pytest.importorskip("tree_sitter")

from torsor_helper.languages import javascript as js  # noqa: E402

TS = """\
import { format } from './dates';
/** Greets someone. */
export function greet(name: string): string { return format(name); }
export const helper = (x: number) => greet(String(x));
export class Widget extends Base {
  // Renders it.
  render() { return greet('x'); }
}
export interface Props { a: number }
export type Id = string;
"""


def _symbols(text, module="app.ts"):
    return {s.name: s for s in js.extract(text, module)[0]}


def test_typescript_definitions():
    syms = _symbols(TS)
    assert syms["greet"].kind == "function" and syms["greet"].line == 3
    assert syms["greet"].signature == "greet(name: string)"
    assert syms["greet"].doc == "Greets someone."
    assert syms["helper"].kind == "function" and syms["helper"].signature == "helper(x: number)"
    assert syms["Widget"].kind == "class"
    assert syms["Widget.render"].kind == "method" and syms["Widget.render"].doc == "Renders it."
    assert syms["Props"].kind == "type" and syms["Id"].kind == "type"


def test_javascript_and_tsx_grammars_are_selected_by_suffix():
    js_syms = _symbols("function run() {}\nclass Svc {}\n", "a.js")
    assert js_syms["run"].kind == "function" and js_syms["Svc"].kind == "class"
    tsx = _symbols("export const App = () => <div/>;\nexport default function Page() { return <App/>; }\n", "p.tsx")
    assert tsx["App"].kind == "function" and tsx["Page"].kind == "function"


def test_syntax_errors_degrade_to_what_parses():
    assert "ok" in _symbols("function ok() {}\nfunction {{{ broken\n")
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run --extra dev --extra languages pytest tests/test_lang_javascript.py -q`
Expected: `ImportError: cannot import name 'javascript'`

- [ ] **Step 4: Write the runner**

```python
# src/torsor_helper/languages/treesitter.py
"""The one module that touches tree_sitter (ADR 0013): grammar loading, parsing
and query helpers shared by every tree-sitter language. Imports are lazy so the
package imports cleanly without the [languages] extra."""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=None)
def grammar(name: str):
    from tree_sitter import Language

    if name == "javascript":
        import tree_sitter_javascript as m
        return Language(m.language())
    if name == "typescript":
        import tree_sitter_typescript as m
        return Language(m.language_typescript())
    if name == "tsx":
        import tree_sitter_typescript as m
        return Language(m.language_tsx())
    if name == "go":
        import tree_sitter_go as m
        return Language(m.language())
    raise KeyError(name)


@lru_cache(maxsize=None)
def _parser(name: str):
    from tree_sitter import Parser

    return Parser(grammar(name))


@lru_cache(maxsize=None)
def _query(name: str, source: str):
    from tree_sitter import Query

    return Query(grammar(name), source)


def parse(name: str, text: str):
    return _parser(name).parse(text.encode("utf-8"))


def captures(name: str, node, query: str) -> dict[str, list]:
    from tree_sitter import QueryCursor

    return QueryCursor(_query(name, query)).captures(node)


def matches(name: str, node, query: str) -> list[dict[str, list]]:
    from tree_sitter import QueryCursor

    return [caps for _pattern, caps in QueryCursor(_query(name, query)).matches(node)]


def text(node) -> str:
    return node.text.decode("utf-8", errors="replace")


def line(node) -> int:
    return node.start_point[0] + 1


def leading_comment(node) -> str:
    """First line of the comment immediately preceding `node` (JSDoc, `//`, `#`),
    stripped of comment syntax — the cross-language analogue of a docstring."""
    prev = node.prev_named_sibling
    if prev is None or prev.type != "comment":
        return ""
    raw = text(prev).strip()
    for lead in ("/**", "/*", "//", "#"):
        if raw.startswith(lead):
            raw = raw[len(lead):]
            break
    first = raw.strip().split("\n", 1)[0].strip()
    return first.lstrip("* ").rstrip("*/ ").strip()


def enclosing(node, types: tuple[str, ...]):
    """Nearest ancestor whose type is in `types`, or None."""
    cur = node.parent
    while cur is not None:
        if cur.type in types:
            return cur
        cur = cur.parent
    return None
```

- [ ] **Step 5: Write the JS/TS extractor (symbols only)**

```python
# src/torsor_helper/languages/javascript.py
"""JavaScript / TypeScript / TSX: symbols, reference edges and relative-import
resolution over the official tree-sitter grammars. Resolves only the two
reliable cases (ADR 0004): same-file top-level definitions and names bound by a
relative `import … from './x'` / `require('./x')`."""
from __future__ import annotations

import posixpath

from torsor_helper.languages import treesitter as ts
from torsor_helper.languages.modules import norm_module
from torsor_helper.models import Symbol, SymbolEdge


def grammar_for(module: str) -> str:
    if module.endswith(".tsx"):
        return "tsx"
    if module.endswith(".ts"):
        return "typescript"
    return "javascript"


# The class name node differs per grammar; everything else is shared.
def _defs_query(grammar: str) -> str:
    class_name = "(type_identifier)" if grammar in ("typescript", "tsx") else "(identifier)"
    q = f"""
(function_declaration name: (identifier) @function.name) @function
(lexical_declaration (variable_declarator name: (identifier) @arrow.name
                       value: [(arrow_function) (function_expression)] @arrow.fn) @arrow)
(class_declaration name: {class_name} @class.name) @class
(method_definition name: (property_identifier) @method.name) @method
"""
    if grammar in ("typescript", "tsx"):
        q += """
(interface_declaration name: (type_identifier) @type.name) @type
(type_alias_declaration name: (type_identifier) @type.name) @type
"""
    return q


_OWNER_TYPES = ("function_declaration", "method_definition", "variable_declarator", "class_declaration")


def _class_name(node) -> str:
    name = node.child_by_field_name("name")
    return ts.text(name) if name is not None else ""


def _params(fn_node) -> str:
    params = fn_node.child_by_field_name("parameters") if fn_node is not None else None
    return ts.text(params) if params is not None else "()"


def extract_symbols(source: str, module: str) -> list[Symbol]:
    grammar = grammar_for(module)
    root = ts.parse(grammar, source).root_node
    out: list[Symbol] = []
    for m in ts.matches(grammar, root, _defs_query(grammar)):
        if "function" in m:
            node, name = m["function"][0], ts.text(m["function.name"][0])
            out.append(Symbol(name=name, kind="function", signature=f"{name}{_params(node)}",
                              module=module, line=ts.line(node), doc=ts.leading_comment(_doc_anchor(node))))
        elif "arrow" in m:
            decl, name, fn = m["arrow"][0], ts.text(m["arrow.name"][0]), m["arrow.fn"][0]
            anchor = decl.parent  # the lexical_declaration (or export_statement above it)
            out.append(Symbol(name=name, kind="function", signature=f"{name}{_params(fn)}",
                              module=module, line=ts.line(decl), doc=ts.leading_comment(_doc_anchor(anchor))))
        elif "class" in m:
            node, name = m["class"][0], ts.text(m["class.name"][0])
            out.append(Symbol(name=name, kind="class", signature=name, module=module,
                              line=ts.line(node), doc=ts.leading_comment(_doc_anchor(node))))
        elif "method" in m:
            node, name = m["method"][0], ts.text(m["method.name"][0])
            owner = ts.enclosing(node, ("class_declaration", "class"))
            cls = _class_name(owner) if owner is not None else ""
            full = f"{cls}.{name}" if cls else name
            out.append(Symbol(name=full, kind="method", signature=f"{name}{_params(node)}", module=module,
                              line=ts.line(node), doc=ts.leading_comment(node)))
        elif "type" in m:
            node, name = m["type"][0], ts.text(m["type.name"][0])
            out.append(Symbol(name=name, kind="type", signature=name, module=module,
                              line=ts.line(node), doc=ts.leading_comment(_doc_anchor(node))))
    return sorted(out, key=lambda s: s.line)


def _doc_anchor(node):
    """`export function f` wraps the declaration in an export_statement, and the
    JSDoc sits before the *export* — so look for the comment there."""
    return node.parent if node.parent is not None and node.parent.type == "export_statement" else node


def extract_edges(source: str, module: str) -> list[SymbolEdge]:
    return []  # Task 3


def extract(source: str, module: str) -> tuple[list[Symbol], list[SymbolEdge]]:
    return extract_symbols(source, module), extract_edges(source, module)
```

Register in `languages/__init__.py` (add the import `from torsor_helper.languages import javascript as _js` and the entries):

```python
    "javascript": LanguageSpec("javascript", (".js", ".jsx", ".mjs", ".cjs"), _js.extract,
                               requires=("tree_sitter", "tree_sitter_javascript")),
    "typescript": LanguageSpec("typescript", (".ts", ".tsx"), _js.extract,
                               requires=("tree_sitter", "tree_sitter_typescript")),
```

- [ ] **Step 6: Run the tests; iterate on query shapes until green**

Run: `uv run --extra dev --extra languages pytest tests/test_lang_javascript.py -q -x`
If a query fails to compile (`QueryError`), print the failing node type with `uv run --extra languages python -c "from torsor_helper.languages import treesitter as ts; print(ts.parse('typescript', open('x.ts').read()).root_node)"` and adjust the node name — never loosen the test.
Expected: 3 passed.

- [ ] **Step 7: Degradation + lint + commit**

Run: `uv run --extra dev pytest -q && uv run --extra dev --extra languages pytest -q && uv run --with ruff ruff check src tests`
Expected: both green (the JS tests skip without the extra).

```bash
git add pyproject.toml src/torsor_helper/languages tests/test_lang_javascript.py
git commit -m "feat(languages): tree-sitter runner and JS/TS/TSX symbol extraction

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: JS/TS edges, import resolution, end-to-end map

**Files:**
- Modify: `src/torsor_helper/languages/javascript.py` (edges), `src/torsor_helper/cartographer.py` (`DEFAULT_IGNORE`), `src/torsor_helper/models.py` (`SymbolEdge.hint`)
- Test: `tests/test_lang_javascript.py` (append), `tests/test_map_multilang.py`

**Interfaces:**
- Produces: `javascript.extract_edges(source, module) -> list[SymbolEdge]`; `javascript.resolve_relative(specifier, module) -> str | None`.

- [ ] **Step 1: Write the failing edge tests**

Append to `tests/test_lang_javascript.py`:

```python
def _edges(text, module="app.ts"):
    return js.extract(text, module)[1]


def test_calls_are_attributed_to_their_enclosing_symbol():
    edges = _edges(TS)
    assert any(e.caller == "greet" and e.referenced_name == "format" and e.role == "call" for e in edges)
    assert any(e.caller == "helper" and e.referenced_name == "greet" for e in edges)
    assert any(e.caller == "Widget.render" and e.referenced_name == "greet" for e in edges)


def test_same_file_and_relative_imports_resolve_bare_does_not():
    edges = {(e.referenced_name, e.resolved_module) for e in _edges(
        "import { a } from './lib/a';\nimport React from 'react';\nimport './pkg';\n"
        "function f() { a(); React.x(); g(); }\nfunction g() {}\n", "src/app.ts")}
    assert ("a", "lib.a") in edges          # relative import → module key
    assert ("g", "app") in edges            # same file → own key (src/ stripped)
    assert not any(name == "x" and mod for name, mod in edges)  # bare package stays unresolved


def test_new_and_extends_are_edges():
    edges = _edges("import Base from '../base';\nclass S extends Base { m() { return new Base(); } }\n", "x/s.ts")
    assert any(e.referenced_name == "Base" and e.role == "read" and e.resolved_module == "base" for e in edges)
    assert any(e.referenced_name == "Base" and e.role == "call" and e.caller == "S.m" for e in edges)


def test_require_binds_like_an_import():
    edges = _edges("const h = require('./helper');\nfunction r() { h(); }\n", "a.js")
    assert any(e.referenced_name == "h" and e.resolved_module == "helper" for e in edges)


def test_resolve_relative_collapses_index_and_rejects_escapes():
    assert js.resolve_relative("./pkg", "src/app.ts") == "pkg"
    assert js.resolve_relative("../x/y.js", "src/a/b.ts") == "x.y"
    assert js.resolve_relative("../../escape", "a.ts") is None
    assert js.resolve_relative("lodash", "a.ts") is None
```

And a new end-to-end file:

```python
# tests/test_map_multilang.py
import pytest

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

pytest.importorskip("tree_sitter")


def _ts_repo(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "dates.ts").write_text("export function formatDate(d: Date) { return d.toISOString(); }\n")
    (tmp_path / "src" / "app.ts").write_text(
        "import { formatDate } from './dates';\nexport function run() { return formatDate(new Date()); }\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.ts").write_text("export function nope() {}\n")
    return store


def test_map_impact_and_find_work_on_typescript(tmp_path):
    store = _ts_repo(tmp_path)
    stats = ops.map_repo(store, TorsorConfig())
    assert stats["modules"] == 2 and stats["symbols"] == 2
    impact = ops.impact(store, TorsorConfig(), "formatDate")
    assert [c["caller"] for c in impact["callers"]] == ["run"]
    hits = ops.find_targets(store, TorsorConfig(), "formatDate", mode="fuzzy", limit=5,
                            include_files=False, include_symbols=True)
    assert hits and hits[0]["name"] == "formatDate"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --extra dev --extra languages pytest tests/test_lang_javascript.py tests/test_map_multilang.py -q`
Expected: the new tests fail (`extract_edges` returns `[]`; `resolve_relative` missing).

- [ ] **Step 3: Add `hint` to `SymbolEdge` and widen `DEFAULT_IGNORE`**

`models.py`:
```python
    resolved_module: str | None = None  # module the name resolves to, or None if best-effort failed
    hint: str | None = None  # language-specific resolution hint (e.g. a Go import path); never persisted
```
`cartographer.py`:
```python
DEFAULT_IGNORE = {
    ".torsor", ".git", ".venv", "venv", "__pycache__", "node_modules",
    "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".eggs",
    ".next", ".turbo", "coverage", "vendor", "target",
}
```

- [ ] **Step 4: Implement edges + resolution**

Replace the `extract_edges` stub in `javascript.py`:

```python
_IMPORTS = """
(import_statement (import_clause (identifier) @name) source: (string) @source)
(import_statement (import_clause (named_imports (import_specifier name: (identifier) @name))) source: (string) @source)
(import_statement (import_clause (namespace_import (identifier) @name)) source: (string) @source)
(variable_declarator name: (identifier) @name
  value: (call_expression function: (identifier) @_req arguments: (arguments (string) @source))
  (#eq? @_req "require"))
"""

_REFS = """
(call_expression function: (identifier) @call)
(new_expression constructor: (identifier) @call)
(class_heritage (identifier) @read)
(call_expression function: (member_expression object: (identifier) @receiver property: (property_identifier) @member))
"""

_DEF_NAMES = """
(function_declaration name: (identifier) @n)
(lexical_declaration (variable_declarator name: (identifier) @n value: [(arrow_function) (function_expression)]))
(class_declaration name: [(identifier) (type_identifier)] @n)
"""


def resolve_relative(specifier: str, module: str) -> str | None:
    """`'./x'` / `'../x'` relative to the importing file → module key (suffix
    stripped, `index` collapsed by norm_module). Bare specifiers and paths that
    climb out of the repo → None (ADR 0004: only the reliable cases)."""
    spec = specifier.strip("'\"`")
    if not spec.startswith("."):
        return None
    rel = posixpath.normpath(posixpath.join(posixpath.dirname(module), spec))
    if rel.startswith(".."):
        return None
    return norm_module(rel)


def _aliases(grammar: str, root, module: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for m in ts.matches(grammar, root, _IMPORTS):
        if "name" in m and "source" in m:
            out[ts.text(m["name"][0])] = resolve_relative(ts.text(m["source"][0]), module)
    return out


def _owner(node) -> str:
    cur = node.parent
    while cur is not None:
        if cur.type == "function_declaration":
            return _class_name(cur)
        if cur.type == "method_definition":
            cls = ts.enclosing(cur, ("class_declaration", "class"))
            name = _class_name(cur)
            return f"{_class_name(cls)}.{name}" if cls is not None else name
        if cur.type == "variable_declarator":
            value = cur.child_by_field_name("value")
            if value is not None and value.type in ("arrow_function", "function_expression"):
                return _class_name(cur)
        if cur.type == "class_declaration":
            return _class_name(cur)
        cur = cur.parent
    return "<module>"


def extract_edges(source: str, module: str) -> list[SymbolEdge]:
    grammar = grammar_for(module)
    root = ts.parse(grammar, source).root_node
    own = norm_module(module)
    top_defs = {ts.text(n) for n in ts.captures(grammar, root, _DEF_NAMES.replace(
        "[(identifier) (type_identifier)]", "(type_identifier)" if grammar != "javascript" else "(identifier)")).get("n", [])}
    aliases = _aliases(grammar, root, module)

    def resolve(name: str) -> str | None:
        if name in top_defs:
            return own
        return aliases.get(name)

    edges: list[SymbolEdge] = []
    caps = ts.captures(grammar, root, _REFS)
    for role in ("call", "read"):
        for node in caps.get(role, []):
            name = ts.text(node)
            edges.append(SymbolEdge(caller=_owner(node), referenced_name=name, role=role,
                                    module=module, resolved_module=resolve(name)))
    # `ns.fn()` where `ns` came from `import * as ns from './x'` → edge to fn in x.
    for receiver, member in zip(caps.get("receiver", []), caps.get("member", [])):
        target = aliases.get(ts.text(receiver))
        edges.append(SymbolEdge(caller=_owner(member), referenced_name=ts.text(member), role="call",
                                module=module, resolved_module=target))
    return edges
```

- [ ] **Step 5: Run; iterate on node names only**

Run: `uv run --extra dev --extra languages pytest tests/test_lang_javascript.py tests/test_map_multilang.py -q -x`
Expected: all pass. If `#eq?` predicates aren't honoured by `matches`, filter in Python: keep the require match only when `ts.text(m["_req"][0]) == "require"`.

- [ ] **Step 6: Full suites, lint, guard, commit**

```bash
uv run --extra dev pytest -q && uv run --extra dev --extra languages pytest -q && uv run --with ruff ruff check src tests && uv run torsor guard --strict
git add src/torsor_helper tests/test_lang_javascript.py tests/test_map_multilang.py
git commit -m "feat(languages): JS/TS reference edges with relative-import resolution; map/impact/find work on TypeScript

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Go extractor with same-package cross-file resolution

**Files:**
- Create: `src/torsor_helper/languages/go.py`
- Modify: `src/torsor_helper/languages/__init__.py` (register), `src/torsor_helper/cartographer.py` (`compute_refs` runs resolvers)
- Test: `tests/test_lang_go.py`

**Interfaces:**
- Produces: `go.extract(source, module)`; `go.resolve_cross_file(symbols, edges) -> None` (fills `resolved_module` in place; idempotent).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lang_go.py
import pytest

pytest.importorskip("tree_sitter")

from torsor_helper.cartographer import compute_refs, scan_repo_with_edges  # noqa: E402
from torsor_helper.languages import go  # noqa: E402

STORE = """\
package svc

import (
\t"fmt"
\t"example.com/app/util"
)

// Store keeps things.
type Store struct{}

// Get fetches one.
func (s *Store) Get(id int) int { return util.Norm(id) }

func New() *Store { fmt.Println("x"); return &Store{} }
"""


def test_go_definitions():
    syms = {s.name: s for s in go.extract(STORE, "svc/store.go")[0]}
    assert syms["Store"].kind == "type" and syms["Store"].doc == "Store keeps things."
    assert syms["Store.Get"].kind == "method" and syms["Store.Get"].signature == "Get(id int)"
    assert syms["New"].kind == "function" and syms["New"].line == 14


def test_go_edges_and_hints():
    edges = go.extract(STORE, "svc/store.go")[1]
    println = next(e for e in edges if e.referenced_name == "Println")
    assert println.resolved_module is None and println.hint == "fmt"
    norm = next(e for e in edges if e.referenced_name == "Norm")
    assert norm.caller == "Store.Get" and norm.hint == "example.com/app/util"
    store_call = next(e for e in edges if e.referenced_name == "Store" and e.role == "call")
    assert store_call.resolved_module == "svc.store"  # same file


def test_same_package_and_repo_package_calls_resolve_via_compute_refs(tmp_path):
    (tmp_path / "svc").mkdir()
    (tmp_path / "util").mkdir()
    (tmp_path / "svc" / "store.go").write_text(STORE)
    (tmp_path / "svc" / "other.go").write_text("package svc\n\nfunc Use() int { return New().Get(1) }\n")
    (tmp_path / "util" / "norm.go").write_text("package util\n\nfunc Norm(n int) int { return n }\n")
    symbols, edges = scan_repo_with_edges(tmp_path)
    new = next(e for e in edges if e.referenced_name == "New" and e.module == "svc/other.go")
    assert new.resolved_module == "svc/store.go"           # same package, other file
    norm = next(e for e in edges if e.referenced_name == "Norm")
    assert norm.resolved_module == "util/norm.go"           # import path tail → repo dir
    refs = {s.name: s.refs for s in symbols}
    assert refs["New"] == 2 and refs["Norm"] == 1 and refs["Store.Get"] == 0
    compute_refs(symbols, edges)                            # idempotent
    assert {s.name: s.refs for s in symbols} == refs
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --extra dev --extra languages pytest tests/test_lang_go.py -q`
Expected: `ImportError: cannot import name 'go'`

- [ ] **Step 3: Implement `go.py`**

```python
# src/torsor_helper/languages/go.py
"""Go: symbols, edges, and the two reliable resolutions (ADR 0004) — same file,
and same *package* (Go's normal case: a call to a function defined in another
file of the same directory), plus `pkg.Fn` where the import path's tail names a
directory in this repo. Stdlib and third-party imports stay unresolved."""
from __future__ import annotations

import posixpath

from torsor_helper.languages import treesitter as ts
from torsor_helper.languages.modules import norm_module
from torsor_helper.models import Symbol, SymbolEdge

_DEFS = """
(function_declaration name: (identifier) @function.name) @function
(method_declaration receiver: (parameter_list (parameter_declaration
    type: [(pointer_type (type_identifier) @method.recv) (type_identifier) @method.recv]))
  name: (field_identifier) @method.name) @method
(type_declaration (type_spec name: (type_identifier) @type.name)) @type
"""
_REFS = """
(call_expression function: (identifier) @call)
(call_expression function: (selector_expression operand: (identifier) @pkg field: (field_identifier) @qualified))
(composite_literal type: (type_identifier) @call)
"""
_IMPORTS = "(import_spec path: (interpreted_string_literal) @path)"


def _params(node) -> str:
    p = node.child_by_field_name("parameters")
    return ts.text(p) if p is not None else "()"


def extract_symbols(source: str, module: str) -> list[Symbol]:
    root = ts.parse("go", source).root_node
    out: list[Symbol] = []
    for m in ts.matches("go", root, _DEFS):
        if "function" in m:
            node, name = m["function"][0], ts.text(m["function.name"][0])
            out.append(Symbol(name=name, kind="function", signature=f"{name}{_params(node)}", module=module,
                              line=ts.line(node), doc=ts.leading_comment(node)))
        elif "method" in m:
            node, name, recv = m["method"][0], ts.text(m["method.name"][0]), ts.text(m["method.recv"][0])
            out.append(Symbol(name=f"{recv}.{name}", kind="method", signature=f"{name}{_params(node)}",
                              module=module, line=ts.line(node), doc=ts.leading_comment(node)))
        elif "type" in m:
            node, name = m["type"][0], ts.text(m["type.name"][0])
            out.append(Symbol(name=name, kind="type", signature=name, module=module,
                              line=ts.line(node), doc=ts.leading_comment(node)))
    return sorted(out, key=lambda s: s.line)


def imports(source: str) -> list[tuple[str, int]]:
    root = ts.parse("go", source).root_node
    return [(ts.text(n).strip('"'), ts.line(n)) for n in ts.captures("go", root, _IMPORTS).get("path", [])]


def _owner(node) -> str:
    fn = ts.enclosing(node, ("function_declaration", "method_declaration"))
    if fn is None:
        return "<module>"
    name = ts.text(fn.child_by_field_name("name"))
    if fn.type == "method_declaration":
        recv = fn.child_by_field_name("receiver")
        tid = next((n for n in _walk(recv) if n.type == "type_identifier"), None)
        return f"{ts.text(tid)}.{name}" if tid is not None else name
    return name


def _walk(node):
    yield node
    for c in node.children:
        yield from _walk(c)


def extract_edges(source: str, module: str) -> list[SymbolEdge]:
    root = ts.parse("go", source).root_node
    own = norm_module(module)
    top = {s.name for s in extract_symbols(source, module) if "." not in s.name}
    # package alias → import path ("util" → "example.com/app/util"); explicit aliases too
    paths: dict[str, str] = {}
    for spec, _line in imports(source):
        paths[spec.rsplit("/", 1)[-1]] = spec
    for n in ts.captures("go", root, "(import_spec name: (package_identifier) @alias path: (interpreted_string_literal) @p)").get("alias", []):
        paths[ts.text(n)] = ts.text(n.next_named_sibling).strip('"')

    edges: list[SymbolEdge] = []
    caps = ts.captures("go", root, _REFS)
    for node in caps.get("call", []):
        name = ts.text(node)
        edges.append(SymbolEdge(caller=_owner(node), referenced_name=name, role="call", module=module,
                                resolved_module=own if name in top else None))
    for pkg, member in zip(caps.get("pkg", []), caps.get("qualified", [])):
        edges.append(SymbolEdge(caller=_owner(member), referenced_name=ts.text(member), role="call",
                                module=module, resolved_module=None, hint=paths.get(ts.text(pkg))))
    return edges


def extract(source: str, module: str) -> tuple[list[Symbol], list[SymbolEdge]]:
    return extract_symbols(source, module), extract_edges(source, module)


def resolve_cross_file(symbols: list[Symbol], edges: list[SymbolEdge]) -> None:
    """Fill `resolved_module` for Go edges the single-file pass couldn't: a bare
    call to a top-level symbol in another file of the same directory, or
    `pkg.Fn` whose import path ends with a directory that exists in the scanned
    repo. Idempotent — only touches edges still unresolved."""
    by_dir: dict[str, dict[str, str]] = {}
    for s in symbols:
        if s.module.endswith(".go") and "." not in s.name:
            by_dir.setdefault(posixpath.dirname(s.module), {})[s.name] = s.module
    dirs = sorted(by_dir, key=len, reverse=True)  # longest suffix wins
    for e in edges:
        if not e.module.endswith(".go") or e.resolved_module is not None:
            continue
        if e.hint:
            target_dir = next((d for d in dirs if d and (e.hint == d or e.hint.endswith("/" + d))), None)
            if target_dir is not None:
                e.resolved_module = by_dir[target_dir].get(e.referenced_name)
            continue
        e.resolved_module = by_dir.get(posixpath.dirname(e.module), {}).get(e.referenced_name)


def complexity(text: str) -> int:
    return 0  # Task 5
```

Register (add `from torsor_helper.languages import go as _go`):
```python
    "go": LanguageSpec("go", (".go",), _go.extract, requires=("tree_sitter", "tree_sitter_go"),
                       cross_file_resolver=_go.resolve_cross_file, imports=_go.imports),
```

In `cartographer.compute_refs`, before the `counts = Counter(...)` line:
```python
    for spec in languages.LANGUAGES.values():
        if spec.cross_file_resolver is not None and languages.is_available(spec.name):
            spec.cross_file_resolver(symbols, edges)
```

- [ ] **Step 4: Run; fix node names only; then full suites + commit**

Run: `uv run --extra dev --extra languages pytest tests/test_lang_go.py -q -x`
Expected: 3 passed. Then:
```bash
uv run --extra dev pytest -q && uv run --extra dev --extra languages pytest -q && uv run --with ruff ruff check src tests && uv run torsor guard --strict
git add src/torsor_helper tests/test_lang_go.py
git commit -m "feat(languages): Go extractor with same-package and repo-package resolution inside compute_refs

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Complexity and churn widen to every registered language

**Files:**
- Modify: `src/torsor_helper/coach/hotspots.py` (`_complexity`, `_churn`), `src/torsor_helper/coach/coupling.py:32`, `src/torsor_helper/languages/javascript.py`, `src/torsor_helper/languages/go.py`, `src/torsor_helper/languages/__init__.py` (complexity on JS/TS/Go specs)
- Test: `tests/test_complexity_multilang.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_complexity_multilang.py
import pytest

from torsor_helper import languages
from torsor_helper.coach.hotspots import _complexity


def test_python_complexity_is_unchanged(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("def f(x):\n    if x:\n        return 1\n    for i in x:\n        pass\n    return 0\n")
    assert _complexity(f) == 6 + 2


def test_unknown_suffix_scores_zero(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("if if if\n")
    assert _complexity(f) == 0


@pytest.mark.skipif(not languages.is_available("typescript"), reason="needs [languages] extra")
def test_typescript_branches_count(tmp_path):
    f = tmp_path / "a.ts"
    f.write_text("function f(x) {\n  if (x) { return 1 }\n  for (const i of x) {}\n  return x && y ? 1 : 0;\n}\n")
    assert _complexity(f) == 5 + 4  # if, for, &&, ternary


@pytest.mark.skipif(not languages.is_available("go"), reason="needs [languages] extra")
def test_go_branches_count(tmp_path):
    f = tmp_path / "a.go"
    f.write_text("package a\nfunc f(x int) int {\n\tif x > 0 { return 1 }\n\tfor i := 0; i < x; i++ {}\n\tswitch x { case 1: }\n\treturn 0\n}\n")
    assert _complexity(f) == 7 + 3  # if, for, case
```

- [ ] **Step 2: Run to verify failure** — `uv run --extra dev --extra languages pytest tests/test_complexity_multilang.py -q`. Expected: the TS/Go tests fail (0), unknown-suffix passes only after the change.

- [ ] **Step 3: Implement**

`javascript.py`:
```python
_BRANCHES = """
[(if_statement) (for_statement) (for_in_statement) (while_statement) (do_statement)
 (switch_case) (catch_clause) (ternary_expression)] @b
(binary_expression operator: ["&&" "||" "??"]) @b
"""


def complexity(text: str) -> int:
    root = ts.parse("javascript", text).root_node
    return text.count("\n") + 1 + len(ts.captures("javascript", root, _BRANCHES).get("b", []))
```
(JS grammar parses the branch structure of TS well enough for a count; using one grammar keeps the proxy stable across `.ts`/`.tsx`/`.js`.)

`go.py`:
```python
_BRANCHES = """
[(if_statement) (for_statement) (expression_case) (type_case) (communication_case) (select_statement)] @b
(binary_expression operator: ["&&" "||"]) @b
"""


def complexity(text: str) -> int:
    root = ts.parse("go", text).root_node
    return text.count("\n") + 1 + len(ts.captures("go", root, _BRANCHES).get("b", []))
```

Registry: add `complexity=_js.complexity` to the javascript and typescript specs, `complexity=_go.complexity` to go.

`coach/hotspots.py`: delete `_DECISION_NODES` and the `ast` import; replace `_complexity` with:
```python
def _complexity(path: Path) -> int:
    return languages.complexity(path)
```
and in `_churn` replace `line.strip().endswith(".py")` with `line.strip().endswith(languages.source_extensions())` (add `from torsor_helper import languages`). Same one-line change at `coach/coupling.py:32`.

- [ ] **Step 4: Run; full suites; commit**

```bash
uv run --extra dev --extra languages pytest tests/test_complexity_multilang.py tests/test_coach_hotspots.py tests/test_coach_trend.py tests/test_coach_coupling.py -q
uv run --extra dev pytest -q && uv run --extra dev --extra languages pytest -q && uv run --with ruff ruff check src tests
git add src/torsor_helper tests/test_complexity_multilang.py
git commit -m "feat(coach): complexity and churn cover every registered language

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: `forbid_import` on JS/TS/Go

**Files:**
- Modify: `src/torsor_helper/guard.py` (`_forbid_import`), `src/torsor_helper/languages/javascript.py` (`imports`), registry (`imports=` on JS/TS specs)
- Test: `tests/test_guard_multilang.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_guard_multilang.py
import pytest

from torsor_helper import languages
from torsor_helper.guard import violations_for_file
from torsor_helper.models import Rule


def _rule(target, scope):
    return Rule(kind="forbid_import", target=target, scope=scope, source="ADR 9", message="no")


@pytest.mark.skipif(not languages.is_available("typescript"), reason="needs [languages] extra")
def test_typescript_forbid_import_matches_specifier_prefix():
    text = "import x from 'lodash/fp';\nimport { db } from '../internal/db';\n"
    assert [v.line for v in violations_for_file("src/a.ts", text, _rule("lodash", "**/*.ts"))] == [1]
    assert [v.line for v in violations_for_file("src/a.ts", text, _rule("../internal", "**/*.ts"))] == [2]
    assert violations_for_file("src/a.ts", text, _rule("react", "**/*.ts")) == []


@pytest.mark.skipif(not languages.is_available("go"), reason="needs [languages] extra")
def test_go_forbid_import_matches_path_prefix():
    text = 'package a\nimport (\n\t"fmt"\n\t"example.com/app/internal/db"\n)\n'
    assert [v.line for v in violations_for_file("a.go", text, _rule("example.com/app/internal", "**/*.go"))] == [4]


def test_non_python_without_extra_is_silent(monkeypatch):
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")
    assert violations_for_file("a.ts", "import x from 'lodash';\n", _rule("lodash", "**/*.ts")) == []
```

- [ ] **Step 2: Run to verify failure** — expected: the TS/Go tests fail with `[]` (ast.parse SyntaxError path returns nothing).

- [ ] **Step 3: Implement**

`javascript.py` — add:
```python
def imports(source: str) -> list[tuple[str, int]]:
    """Every import/require specifier with its line, for guard/deps. Uses the
    javascript grammar for all three dialects: import syntax is identical."""
    root = ts.parse("javascript", source).root_node
    out: list[tuple[str, int]] = []
    for m in ts.matches("javascript", root, _IMPORTS):
        if "source" in m:
            out.append((ts.text(m["source"][0]).strip("'\"`"), ts.line(m["source"][0])))
    for n in ts.captures("javascript", root, "(import_statement source: (string) @s)").get("s", []):
        pair = (ts.text(n).strip("'\"`"), ts.line(n))
        if pair not in out:
            out.append(pair)  # side-effect imports (`import './pkg'`) have no clause
    return sorted(set(out), key=lambda p: p[1])
```
Registry: `imports=_js.imports` on javascript and typescript.

`guard.py` — at the top of `_forbid_import`:
```python
    if not relpath.endswith(".py"):
        return _forbid_import_specifiers(relpath, text, rule)
```
and add:
```python
def _forbid_import_specifiers(relpath: str, text: str, rule: Rule) -> list[Violation]:
    """Non-Python: match the rule's target as a prefix of the import specifier
    string ('lodash', '../internal/db', 'example.com/app/internal'). Silent
    when the language isn't available — never an error."""
    from torsor_helper import languages

    target = rule.target.rstrip("/")
    out: list[Violation] = []
    for spec, line in languages.import_specifiers(relpath, text):
        if spec == target or spec.startswith(target + "/") or spec.startswith(target + "."):
            out.append(_violation(rule, relpath, line, f"imports forbidden module '{spec}'"))
    return out
```

- [ ] **Step 4: Run; full suites; commit**

```bash
uv run --extra dev --extra languages pytest tests/test_guard_multilang.py tests/test_guard_checks.py -q
uv run --extra dev pytest -q && uv run --extra dev --extra languages pytest -q && uv run --with ruff ruff check src tests && uv run torsor guard --strict
git add src/torsor_helper tests/test_guard_multilang.py
git commit -m "feat(guard): forbid_import rules apply to JS/TS/Go import specifiers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Discoverability — doctor, map summary, Coach `uncharted_language`

**Files:**
- Modify: `src/torsor_helper/cli.py` (`doctor`, `map`), `src/torsor_helper/operations.py` (`map_repo` returns `languages`), `src/torsor_helper/coach/health.py`
- Test: `tests/test_multilang_discoverability.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_multilang_discoverability.py
from typer.testing import CliRunner

from torsor_helper import languages
from torsor_helper.cli import app
from torsor_helper.coach import health
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def test_doctor_lists_language_availability(tmp_path, monkeypatch):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")
    r = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert r.exit_code == 0
    assert "python: ready" in r.output
    assert "typescript: install torsor-helper[languages]" in r.output


def test_map_summary_reports_per_language_counts(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "a.py").write_text("def f():\n    pass\n")
    r = runner.invoke(app, ["map", "--root", str(tmp_path)])
    assert "python 1" in r.output


def test_uncharted_language_rec_when_extra_missing(tmp_path, monkeypatch):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "src").mkdir()
    for i in range(6):
        (tmp_path / "src" / f"m{i}.ts").write_text("export const x = 1;\n")
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")
    recs = health.check_uncharted_language(store)
    assert len(recs) == 1 and recs[0].kind == "uncharted_language"
    assert "typescript" in recs[0].message and "[languages]" in recs[0].action


def test_no_uncharted_language_rec_below_threshold_or_when_available(tmp_path, monkeypatch):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "a.ts").write_text("export const x = 1;\n")
    monkeypatch.setattr(languages, "is_available", lambda name: name == "python")
    assert health.check_uncharted_language(store) == []
    monkeypatch.setattr(languages, "is_available", lambda name: True)
    for i in range(6):
        (tmp_path / f"m{i}.ts").write_text("export const x = 1;\n")
    assert health.check_uncharted_language(store) == []
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

`health.py`:
```python
_UNCHARTED_LANGUAGE_MIN_FILES = 5


def check_uncharted_language(store: Store) -> list[Recommendation]:
    """A language with real presence in the repo but no available extractor —
    the map is silently blind to it. Index-free and deterministic."""
    from torsor_helper import languages

    counts: dict[str, int] = {}
    for path in store.paths.root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(store.paths.root).parts
        if any(part in cartographer.DEFAULT_IGNORE or part.startswith(".") for part in rel[:-1]):
            continue
        for spec in languages.LANGUAGES.values():
            if path.suffix in spec.extensions and not languages.is_available(spec.name):
                counts[spec.name] = counts.get(spec.name, 0) + 1
    out: list[Recommendation] = []
    for name, n in sorted(counts.items()):
        if n >= _UNCHARTED_LANGUAGE_MIN_FILES:
            out.append(Recommendation(
                kind="uncharted_language", severity="info",
                message=f"{n} {name} file(s) are invisible to the map — the [languages] extra isn't installed.",
                action="uv tool install 'torsor-helper[languages]'", source=name, key=f"uncharted_language:{name}",
            ))
    return out
```
Add `*check_uncharted_language(store),` to `run_health`.

`operations.map_repo`: in both return dicts add `"languages": _language_counts(symbols_or_conn)`. Add:
```python
def _language_counts(modules) -> dict[str, int]:
    from torsor_helper import languages

    counts: dict[str, int] = {}
    for m in modules:
        spec = languages.spec_for(m)
        if spec is not None:
            counts[spec.name] = counts.get(spec.name, 0) + 1
    return counts
```
Use `db.modules(conn)` in the skipped branch and `{s.module for s in symbols}` in the scanned branch.

`cli.map`: append to both echo lines: `" · " + ", ".join(f"{k} {v}" for k, v in stats["languages"].items())`.

`cli.doctor`, before the final `OK` echo:
```python
    from torsor_helper import languages

    for name, ok in languages.available().items():
        typer.echo(f"{name}: {'ready' if ok else 'install torsor-helper[languages]'}")
```

- [ ] **Step 4: Run; full suites; commit** — `git commit -m "feat: doctor/map/Coach surface which languages the map can see"`.

---

### Task 8: ADR 0013, CI axis, docs, version 0.7.0

**Files:**
- Create: `.torsor/architecture/decisions/0013-python-stays-on-stdlib-ast-other-languages-use-official-tree-sitter-grammar-wheels-never-the-language-pack.md`
- Modify: `.github/workflows/ci.yml`, `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `src/torsor_helper/__init__.py`, `.torsor/architecture/decisions/0003-…md` (`status: superseded`)

- [ ] **Step 1: ADR 0013** (frontmatter rules are the enforcement):

```yaml
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
```
Body: Context (ADR 0003's objection was the binding's instability; 0.25+ is stable; the pack fetches ~25 MB at first use — measured 2026-09-04), Decision (registry; official wheels as `[languages]` extra; Python keeps `ast`), Consequences (Python-only behaviour unchanged without the extra; adding a language = one wheel + one query module). Set ADR 0003 `status: superseded`.

- [ ] **Step 2: CI** — replace the `Test` step with two:
```yaml
      - name: Test (no extras — proves degradation)
        run: uv run --extra dev pytest -q
      - name: Test (with languages extra)
        run: uv run --extra dev --extra languages pytest -q
```

- [ ] **Step 3: Docs** — README: install line `uv tool install "torsor-helper[languages]"`; the "Python-only today" sentence at README:484 becomes "Python via stdlib `ast`; JavaScript/TypeScript/Go via the `[languages]` extra (official tree-sitter grammar wheels, offline)"; `torsor map` row mentions languages. CLAUDE.md: replace the cartographer bullet's "stdlib-ast … not tree-sitter (ADR 0003)" with the registry description and ADR 0013. CHANGELOG `## [Unreleased]` → `## [0.7.0] — Polyglot Map (date)` with sections for languages, guard widening, discoverability. `__version__ = "0.7.0"`.

- [ ] **Step 4: Verify everything and commit**

```bash
uv run --extra dev pytest -q && uv run --extra dev --extra languages pytest -q && uv run --with ruff ruff check src tests && uv run torsor guard --strict && uv run torsor rules --scoped
git add -A .torsor/architecture .claude/rules/torsor .github README.md CLAUDE.md CHANGELOG.md src/torsor_helper/__init__.py
git commit -m "release: v0.7.0 — polyglot map (ADR 0013)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9 (Phase 2): `deps` for JavaScript/TypeScript

**Files:**
- Modify: `src/torsor_helper/deps.py`
- Test: `tests/test_deps_multilang.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_deps_multilang.py
import json

import pytest

from torsor_helper import deps, languages

needs_ts = pytest.mark.skipif(not languages.is_available("typescript"), reason="needs [languages] extra")


@needs_ts
def test_js_phantom_bare_specifier(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"lodash": "^4"}, "devDependencies": {"@types/node": "*"}}))
    (tmp_path / "node_modules" / "@scope" / "pkg").mkdir(parents=True)
    (tmp_path / "a.ts").write_text(
        "import _ from 'lodash/fp';\nimport fs from 'node:fs';\nimport path from 'path';\n"
        "import x from '@scope/pkg/sub';\nimport { y } from './local';\nimport ghost from 'left-padd';\n")
    unknown = deps.unknown_imports(tmp_path, ["a.ts"])
    assert [(u["name"], u["line"]) for u in unknown] == [("left-padd", 6)]
```

- [ ] **Step 2: Run to verify failure** (expected: `[]` — non-Python files are ignored today).

- [ ] **Step 3: Implement** in `deps.py`:

```python
_NODE_BUILTINS = {
    "assert", "async_hooks", "buffer", "child_process", "cluster", "console", "constants", "crypto", "dgram",
    "diagnostics_channel", "dns", "domain", "events", "fs", "http", "http2", "https", "inspector", "module",
    "net", "os", "path", "perf_hooks", "process", "punycode", "querystring", "readline", "repl", "stream",
    "string_decoder", "sys", "timers", "tls", "trace_events", "tty", "url", "util", "v8", "vm", "wasi",
    "worker_threads", "zlib", "test",
}


def _js_package(spec: str) -> str | None:
    """Bare specifier → package name ('lodash/fp' → 'lodash', '@s/p/x' → '@s/p');
    None for relative/absolute paths and node: builtins."""
    if spec.startswith((".", "/", "node:")):
        return None
    parts = spec.split("/")
    return "/".join(parts[:2]) if spec.startswith("@") and len(parts) >= 2 else parts[0]


def _js_known(root: Path) -> set[str]:
    known = set(_NODE_BUILTINS)
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            data = {}
        for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            known.update((data.get(key) or {}).keys())
    nm = root / "node_modules"
    if nm.is_dir():
        for entry in nm.iterdir():
            if entry.name.startswith("@") and entry.is_dir():
                known.update(f"{entry.name}/{sub.name}" for sub in entry.iterdir() if sub.is_dir())
            elif entry.is_dir():
                known.add(entry.name)
    return known


def _unknown_js_imports(root: Path, relpath: str, text: str) -> list[dict]:
    from torsor_helper import languages

    known = _js_known(root)
    out = []
    for spec, line in languages.import_specifiers(relpath, text):
        name = _js_package(spec)
        if name and name not in known:
            out.append({"file": relpath, "line": line, "name": name})
    return out
```
In `unknown_imports`, dispatch per file: `.js/.jsx/.mjs/.cjs/.ts/.tsx` → `_unknown_js_imports`, `.go` → `_unknown_go_imports` (Task 10), else the existing Python path. Add `import json` at the top.

- [ ] **Step 4: Run; suites; commit** — `git commit -m "feat(deps): phantom-import check for JavaScript/TypeScript"`.

---

### Task 10 (Phase 2): `deps` for Go

**Files:**
- Modify: `src/torsor_helper/deps.py`
- Test: `tests/test_deps_multilang.py` (append)

- [ ] **Step 1: Failing test**

```python
needs_go = pytest.mark.skipif(not languages.is_available("go"), reason="needs [languages] extra")


@needs_go
def test_go_phantom_import_path(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/app\n\ngo 1.22\n\nrequire (\n\tgithub.com/real/lib v1.0.0\n)\n")
    (tmp_path / "a.go").write_text(
        'package a\nimport (\n\t"fmt"\n\t"example.com/app/util"\n\t"github.com/real/lib/sub"\n\t"github.com/ghost/pkg"\n)\n')
    unknown = deps.unknown_imports(tmp_path, ["a.go"])
    assert [(u["name"], u["line"]) for u in unknown] == [("github.com/ghost/pkg", 6)]
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

```python
_GO_REQUIRE = re.compile(r"^\s*([A-Za-z0-9._~-]+(?:/[A-Za-z0-9._~-]+)+)\s+v", re.M)
_GO_MODULE = re.compile(r"^module\s+(\S+)", re.M)


def _go_known_prefixes(root: Path) -> list[str]:
    mod = root / "go.mod"
    if not mod.exists():
        return []
    try:
        text = mod.read_text(encoding="utf-8")
    except OSError:
        return []
    prefixes = _GO_REQUIRE.findall(text)
    m = _GO_MODULE.search(text)
    if m:
        prefixes.append(m.group(1))
    return prefixes


def _unknown_go_imports(root: Path, relpath: str, text: str) -> list[dict]:
    from torsor_helper import languages

    prefixes = _go_known_prefixes(root)
    out = []
    for spec, line in languages.import_specifiers(relpath, text):
        if "." not in spec.split("/", 1)[0]:
            continue  # stdlib: first segment has no dot
        if any(spec == p or spec.startswith(p + "/") for p in prefixes):
            continue
        out.append({"file": relpath, "line": line, "name": spec})
    return out
```
(`re` is already imported in `deps.py`; add if not.)

- [ ] **Step 4: Run; suites; docs line in README `deps` row ("Python, JS/TS, Go"); commit** — `git commit -m "feat(deps): phantom-import check for Go"`.

---

## Self-review notes

- **Spec coverage:** registry/extractors (T1–T4), consumers for free via `iter_source_files` (T1), complexity (T5), `forbid_import` (T6), doctor/map/Coach discoverability (T7), ADR 0013 + CI + packaging + version (T8), Phase 2 deps (T9–T10). `DEFAULT_IGNORE` additions (T3). `require_import`/`forbid_layer_import` stay Python-only — documented in T8's README text.
- **Deviation from spec, deliberate:** Go `pkg.Fn` resolution uses the import path's directory *suffix* against directories present in the scanned repo instead of parsing `go.mod`'s `module` line — same result whenever `go.mod` exists, works without it, and needs no root access inside the resolver. Task 10 still reads `go.mod` for `deps`.
- **Type consistency:** `LanguageSpec.imports: Callable[[str], list[tuple[str, int]]]` (T1) ⇄ `javascript.imports`/`go.imports` (T4, T6) ⇄ `languages.import_specifiers(relpath, text)` (T1) used by guard (T6) and deps (T9–T10). `SymbolEdge.hint` (T3) ⇄ Go resolver (T4). `languages.complexity(path)` (T1) ⇄ `hotspots._complexity` (T5).
