# torsor-helper Phase 3 (Map) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the agent architectural awareness — a symbol-level repository map (Markdown under `map/`) plus a queryable symbol inventory in the index — exposed through `map_repo()` and `get_intent()` MCP tools and a `torsor map` CLI.

**Architecture:** A `cartographer` parses the project's Python source with the **stdlib `ast` module** (zero-dependency, deterministic) into `Symbol` records (function/class/method, signature, module, line, docstring, reference count). `map_repo` renders those into committed `map/overview.md` + `map/modules/*.md`, stores them in a `symbols` table in the derived index, and reindexes. `get_intent` assembles the architecture tier (system-patterns + tech-context + ADRs) plus the symbols relevant to a topic. `operations`/`server`/`cli` stay thin adapters.

**Tech Stack:** Python ≥3.11 stdlib `ast`; builds on Phase-1/2 `store`/`db`/`models`/`operations`/`config`/`budget`.

**Key design decision — `ast`, not tree-sitter (refinement of the spec):** the `tree-sitter` + `tree-sitter-language-pack` combo available today ships an unstable, mutually-incompatible binding (node methods vs. the official `Query`/`QueryCursor`), which is too fragile to build on. Python's stdlib `ast` extracts exactly what the map needs for the dogfood language with no dependency and full reliability. Multi-language support via a pinned tree-sitter binding is a documented fast-follow (Phase 3.x), gated behind a `LanguageSpec` registry so adding a language is data, not rework. This also keeps the toolkit small (no new deps in Phase 3).

---

## File Structure

```
src/torsor_helper/cartographer.py   # extract_symbols (ast) · iter_source_files · scan_repo · render_map
src/torsor_helper/models.py         # MODIFY: add Symbol
src/torsor_helper/db.py             # MODIFY: symbols table + replace_all_symbols / search_symbols / modules
src/torsor_helper/operations.py     # MODIFY: add map_repo() and get_intent()
src/torsor_helper/server.py         # MODIFY: register map_repo + get_intent tools
src/torsor_helper/cli.py            # MODIFY: add `torsor map`
tests/test_cartographer_extract.py
tests/test_cartographer_scan.py
tests/test_cartographer_render.py
tests/test_db_symbols.py
tests/test_map_repo.py
tests/test_get_intent.py
tests/test_server_map_intent.py
tests/test_cli_map.py
```

## Interface contracts (locked — use these exact names)

- `models.Symbol(BaseModel)`: `name:str`, `kind:str` ("function"|"class"|"method"), `signature:str`, `module:str`, `line:int`, `doc:str=""`, `refs:int=0`.
- `cartographer.DEFAULT_IGNORE: set[str]`; `cartographer.extract_symbols(source:str, module:str) -> list[Symbol]`; `cartographer.iter_source_files(root:Path, ignore=DEFAULT_IGNORE) -> list[Path]`; `cartographer.scan_repo(root:Path, paths:list[str]|None=None, ignore=DEFAULT_IGNORE) -> list[Symbol]`; `cartographer.render_map(symbols:list[Symbol], *, overview_tokens:int=2000, chars_per_token:int=4) -> dict[str, tuple[str,str]]` (relpath → (title, body)).
- `db.replace_all_symbols(conn, symbols)`; `db.search_symbols(conn, query, limit=10) -> list[Symbol]`; `db.modules(conn) -> list[str]`; `db.SCHEMA_VERSION == 2`.
- `operations.map_repo(store, config, paths:list[str]|None=None) -> dict` (`{"modules", "symbols"}`); `operations.get_intent(store, config, topic:str|None=None) -> str`.
- `server` tools: `map_repo(paths: list[str] | None = None) -> str`, `get_intent(topic: str = "") -> str`.

---

### Task 1: Symbol model + `extract_symbols` (ast)

**Files:**
- Modify: `src/torsor_helper/models.py`
- Create: `src/torsor_helper/cartographer.py`
- Create: `tests/test_cartographer_extract.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cartographer_extract.py
from torsor_helper.cartographer import extract_symbols
from torsor_helper.models import Symbol


SRC = '''"""Module."""
import os


def format_date(d, fmt="iso"):
    "Format a date."
    return d


class Cartographer:
    """Maps a repo."""

    def mapit(self, root):
        return root

    async def scan(self, paths=None):
        pass
'''


def test_extract_functions_classes_methods():
    syms = extract_symbols(SRC, "pkg/mod.py")
    by_name = {s.name: s for s in syms}
    assert by_name["format_date"].kind == "function"
    assert by_name["format_date"].signature == "format_date(d, fmt='iso')"
    assert by_name["format_date"].doc == "Format a date."
    assert by_name["Cartographer"].kind == "class"
    assert by_name["Cartographer.mapit"].kind == "method"
    assert by_name["Cartographer.scan"].kind == "method"
    assert all(s.module == "pkg/mod.py" for s in syms)
    assert by_name["format_date"].line == 5


def test_extract_returns_empty_on_syntax_error():
    assert extract_symbols("def broken(:\n", "x.py") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_cartographer_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.cartographer'`

- [ ] **Step 3: Implement**

Add `Symbol` to `src/torsor_helper/models.py` (after `RecallResult`):
```python
class Symbol(BaseModel):
    name: str
    kind: str  # "function" | "class" | "method"
    signature: str
    module: str
    line: int
    doc: str = ""
    refs: int = 0
```

Create `src/torsor_helper/cartographer.py`:
```python
from __future__ import annotations

import ast
from pathlib import Path

from torsor_helper.models import Symbol

DEFAULT_IGNORE = {
    ".torsor", ".git", ".venv", "venv", "__pycache__", "node_modules",
    "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".eggs",
}


def _signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        return f"{fn.name}({ast.unparse(fn.args)})"
    except Exception:
        return f"{fn.name}(...)"


def _first_line(text: str | None) -> str:
    return (text or "").strip().split("\n", 1)[0]


def extract_symbols(source: str, module: str) -> list[Symbol]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out: list[Symbol] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(Symbol(
                name=node.name, kind="function", signature=_signature(node),
                module=module, line=node.lineno, doc=_first_line(ast.get_docstring(node)),
            ))
        elif isinstance(node, ast.ClassDef):
            out.append(Symbol(
                name=node.name, kind="class", signature=node.name,
                module=module, line=node.lineno, doc=_first_line(ast.get_docstring(node)),
            ))
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append(Symbol(
                        name=f"{node.name}.{member.name}", kind="method",
                        signature=_signature(member), module=module, line=member.lineno,
                        doc=_first_line(ast.get_docstring(member)),
                    ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_cartographer_extract.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/models.py src/torsor_helper/cartographer.py tests/test_cartographer_extract.py
git commit -m "feat: Symbol model + ast-based symbol extraction"
```

---

### Task 2: `scan_repo` (walk + ignore + reference counts)

**Files:**
- Modify: `src/torsor_helper/cartographer.py`
- Create: `tests/test_cartographer_scan.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cartographer_scan.py
from torsor_helper.cartographer import iter_source_files, scan_repo


def _make_repo(root):
    (root / "pkg").mkdir()
    (root / "pkg" / "dates.py").write_text("def format_date(d):\n    return d\n")
    (root / "app.py").write_text("from pkg.dates import format_date\n\ndef run():\n    return format_date(1)\n")
    # ignored dirs must be skipped
    (root / ".venv").mkdir()
    (root / ".venv" / "junk.py").write_text("def should_not_appear():\n    pass\n")
    (root / ".torsor").mkdir()
    (root / ".torsor" / "x.py").write_text("def nope():\n    pass\n")


def test_iter_source_files_skips_ignored(tmp_path):
    _make_repo(tmp_path)
    files = [p.relative_to(tmp_path).as_posix() for p in iter_source_files(tmp_path)]
    assert "app.py" in files
    assert "pkg/dates.py" in files
    assert not any(".venv" in f or ".torsor" in f for f in files)


def test_scan_repo_collects_symbols_and_refs(tmp_path):
    _make_repo(tmp_path)
    syms = scan_repo(tmp_path)
    names = {s.name for s in syms}
    assert {"format_date", "run"} <= names
    assert "should_not_appear" not in names
    # format_date is referenced from app.py (import + call) -> refs > 0
    fmt = next(s for s in syms if s.name == "format_date")
    assert fmt.refs >= 1
    assert fmt.module == "pkg/dates.py"


def test_scan_repo_explicit_paths(tmp_path):
    _make_repo(tmp_path)
    syms = scan_repo(tmp_path, paths=["app.py"])
    assert {s.module for s in syms} == {"app.py"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_cartographer_scan.py -v`
Expected: FAIL — `ImportError: cannot import name 'iter_source_files'`

- [ ] **Step 3: Implement — append to `cartographer.py`**

```python
def iter_source_files(root: Path, ignore: set[str] = DEFAULT_IGNORE) -> list[Path]:
    root = Path(root)
    out: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        rel_parts = path.relative_to(root).parts
        if any(part in ignore for part in rel_parts):
            continue
        out.append(path)
    return out


def scan_repo(root: Path, paths: list[str] | None = None, ignore: set[str] = DEFAULT_IGNORE) -> list[Symbol]:
    root = Path(root)
    if paths is not None:
        files = [(root / p) if not Path(p).is_absolute() else Path(p) for p in paths]
    else:
        files = iter_source_files(root, ignore)

    texts: dict[str, str] = {}
    symbols: list[Symbol] = []
    for file in files:
        file = Path(file)
        try:
            src = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            module = file.relative_to(root).as_posix()
        except ValueError:
            module = file.name
        texts[module] = src
        symbols.extend(extract_symbols(src, module))

    blob = "\n".join(texts.values())
    for sym in symbols:
        base = sym.name.split(".")[-1]
        sym.refs = max(0, blob.count(base) - 1)  # minus the definition itself
    return symbols
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_cartographer_scan.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/cartographer.py tests/test_cartographer_scan.py
git commit -m "feat: scan_repo with ignore dirs and reference counting"
```

---

### Task 3: `render_map` (overview + per-module Markdown)

**Files:**
- Modify: `src/torsor_helper/cartographer.py`
- Create: `tests/test_cartographer_render.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cartographer_render.py
from torsor_helper.cartographer import render_map
from torsor_helper.models import Symbol


def _syms():
    return [
        Symbol(name="format_date", kind="function", signature="format_date(d)", module="pkg/dates.py", line=1, doc="Format.", refs=3),
        Symbol(name="Cartographer", kind="class", signature="Cartographer", module="pkg/cart.py", line=1, doc="Maps.", refs=1),
        Symbol(name="Cartographer.mapit", kind="method", signature="mapit(self, root)", module="pkg/cart.py", line=3, refs=0),
    ]


def test_render_map_overview_and_modules():
    out = render_map(_syms())
    assert "overview.md" in out
    title, body = out["overview.md"]
    assert title == "Repository Map"
    assert "pkg/dates.py" in body and "pkg/cart.py" in body
    # per-module files use a path-safe key
    assert "modules/pkg__dates.py.md" in out
    mod_title, mod_body = out["modules/pkg__cart.py.md"]
    assert mod_title == "pkg/cart.py"
    assert "mapit(self, root)" in mod_body
    assert "L3" in mod_body


def test_render_map_empty():
    out = render_map([])
    assert "overview.md" in out
    assert out["overview.md"][0] == "Repository Map"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_cartographer_render.py -v`
Expected: FAIL — `ImportError: cannot import name 'render_map'`

- [ ] **Step 3: Implement — append to `cartographer.py`** (add the import at the top of the file too)

At the top of `cartographer.py`, add:
```python
from torsor_helper.budget import truncate_to_tokens
```
Append:
```python
def render_map(symbols: list[Symbol], *, overview_tokens: int = 2000, chars_per_token: int = 4) -> dict[str, tuple[str, str]]:
    by_module: dict[str, list[Symbol]] = {}
    for sym in symbols:
        by_module.setdefault(sym.module, []).append(sym)

    out: dict[str, tuple[str, str]] = {}

    overview_lines = ["Modules and their key symbols (ranked by references).", ""]
    for module in sorted(by_module):
        syms = sorted(by_module[module], key=lambda s: (-s.refs, s.line))
        overview_lines.append(f"- **{module}** — {len(syms)} symbol(s)")
        for sym in syms[:5]:
            overview_lines.append(f"  - `{sym.signature}` ({sym.kind})")
    overview = truncate_to_tokens("\n".join(overview_lines), overview_tokens, chars_per_token)
    out["overview.md"] = ("Repository Map", overview)

    for module in sorted(by_module):
        syms = sorted(by_module[module], key=lambda s: s.line)
        lines = [f"Symbols in `{module}`.", ""]
        for sym in syms:
            doc = f" — {sym.doc}" if sym.doc else ""
            lines.append(f"- L{sym.line} `{sym.signature}` ({sym.kind}){doc}")
        safe = module.replace("/", "__")
        out[f"modules/{safe}.md"] = (module, "\n".join(lines))

    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_cartographer_render.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/cartographer.py tests/test_cartographer_render.py
git commit -m "feat: render_map (overview + per-module Markdown)"
```

---

### Task 4: `symbols` table + db helpers

**Files:**
- Modify: `src/torsor_helper/db.py`
- Create: `tests/test_db_symbols.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db_symbols.py
from torsor_helper import db
from torsor_helper.models import Symbol


def _conn(tmp_path):
    return db.connect(tmp_path / "torsor.db")


def _syms():
    return [
        Symbol(name="format_date", kind="function", signature="format_date(d)", module="dates.py", line=1, doc="Format a date.", refs=3),
        Symbol(name="Cartographer", kind="class", signature="Cartographer", module="cart.py", line=1, refs=1),
    ]


def test_schema_version_is_2_and_symbols_table_exists(tmp_path):
    conn = _conn(tmp_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "symbols" in tables
    assert int(db.meta_get(conn, "schema_version")) == db.SCHEMA_VERSION == 2


def test_replace_all_symbols_is_idempotent(tmp_path):
    conn = _conn(tmp_path)
    db.replace_all_symbols(conn, _syms())
    db.replace_all_symbols(conn, _syms())  # replace, not append
    assert sorted(db.modules(conn)) == ["cart.py", "dates.py"]


def test_search_symbols_by_name_and_signature(tmp_path):
    conn = _conn(tmp_path)
    db.replace_all_symbols(conn, _syms())
    hits = db.search_symbols(conn, "date")
    assert any(s.name == "format_date" for s in hits)
    assert all(isinstance(s, Symbol) for s in hits)
    assert db.search_symbols(conn, "   ") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_db_symbols.py -v`
Expected: FAIL — `AttributeError: module 'torsor_helper.db' has no attribute 'replace_all_symbols'` (and schema_version assertion)

- [ ] **Step 3: Implement — edit `db.py`**

Change `SCHEMA_VERSION = 1` to `SCHEMA_VERSION = 2`. Add the `symbols` table to the `executescript` in `_create_schema` (it uses `CREATE TABLE IF NOT EXISTS`, so this is additive for existing dbs):
```sql
        CREATE TABLE IF NOT EXISTS symbols (
            name TEXT, kind TEXT, signature TEXT, module TEXT,
            line INTEGER, doc TEXT, refs INTEGER NOT NULL DEFAULT 0
        );
```
Add `from torsor_helper.models import Symbol` to the imports. Append these helpers:
```python
def replace_all_symbols(conn, symbols):
    conn.execute("DELETE FROM symbols")
    conn.executemany(
        "INSERT INTO symbols(name, kind, signature, module, line, doc, refs) VALUES(?,?,?,?,?,?,?)",
        [(s.name, s.kind, s.signature, s.module, s.line, s.doc, s.refs) for s in symbols],
    )
    conn.commit()


def search_symbols(conn, query, limit=10):
    terms = [t for t in re.findall(r"\w+", query.lower()) if t]
    if not terms:
        return []
    clause = " OR ".join(["(lower(name) LIKE ? OR lower(signature) LIKE ? OR lower(doc) LIKE ?)"] * len(terms))
    args: list = []
    for term in terms:
        like = f"%{term}%"
        args += [like, like, like]
    rows = conn.execute(
        f"SELECT name, kind, signature, module, line, doc, refs FROM symbols "
        f"WHERE {clause} ORDER BY refs DESC, name LIMIT ?",
        (*args, limit),
    ).fetchall()
    return [
        Symbol(name=r["name"], kind=r["kind"], signature=r["signature"],
               module=r["module"], line=r["line"], doc=r["doc"] or "", refs=r["refs"])
        for r in rows
    ]


def modules(conn):
    return [r["module"] for r in conn.execute("SELECT DISTINCT module FROM symbols ORDER BY module")]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_db_symbols.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full suite** (the schema bump must not break existing db tests)

Run: `uv run --extra dev pytest -q`
Expected: PASS (all green). NOTE: `tests/test_db.py::test_connect_creates_schema_and_version` asserts `db.meta_get(conn,"schema_version") == db.SCHEMA_VERSION` — it reads `SCHEMA_VERSION` dynamically, so bumping to 2 keeps it green for fresh dbs.

- [ ] **Step 6: Commit**

```bash
git add src/torsor_helper/db.py tests/test_db_symbols.py
git commit -m "feat: symbols table + search/modules helpers (schema v2)"
```

---

### Task 5: `operations.map_repo`

**Files:**
- Modify: `src/torsor_helper/operations.py`
- Create: `tests/test_map_repo.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_map_repo.py
from datetime import datetime

from torsor_helper import db, operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _project(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    (tmp_path / "app.py").write_text(
        "def format_date(d):\n    return d\n\nclass Service:\n    def handle(self, req):\n        return req\n"
    )
    return store


def test_map_repo_writes_map_and_stores_symbols(tmp_path):
    store = _project(tmp_path)
    stats = ops.map_repo(store, TorsorConfig())
    assert stats["symbols"] >= 3  # format_date, Service, Service.handle
    assert stats["modules"] >= 1
    # committed Markdown map exists
    assert store.paths.map_overview.exists()
    assert "app.py" in store.paths.map_overview.read_text()
    # symbols persisted in the index
    conn = db.connect(store.paths.index_db)
    try:
        assert any(s.name == "format_date" for s in db.search_symbols(conn, "format_date"))
        assert "app.py" in db.modules(conn)
    finally:
        conn.close()


def test_map_repo_is_repeatable(tmp_path):
    store = _project(tmp_path)
    ops.map_repo(store, TorsorConfig())
    stats = ops.map_repo(store, TorsorConfig())  # re-run replaces, doesn't duplicate
    conn = db.connect(store.paths.index_db)
    try:
        fmt = db.search_symbols(conn, "format_date")
        assert len([s for s in fmt if s.name == "format_date"]) == 1
    finally:
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_map_repo.py -v`
Expected: FAIL — `AttributeError: module 'torsor_helper.operations' has no attribute 'map_repo'`

- [ ] **Step 3: Implement — add to `operations.py`**

Add the import (with the other `from torsor_helper import ...`):
```python
from torsor_helper import cartographer
```
Append:
```python
def map_repo(store: Store, config: TorsorConfig, paths: list[str] | None = None) -> dict:
    symbols = cartographer.scan_repo(store.paths.root, paths)
    rendered = cartographer.render_map(
        symbols,
        overview_tokens=config.budgets.bootstrap_tokens,
        chars_per_token=config.budgets.chars_per_token,
    )
    for relpath, (title, body) in rendered.items():
        target = store.paths.map_dir / relpath
        store.write_note(target, Frontmatter(type="map", status="derived", tags=["map"]), title, body)

    conn = db.connect(store.paths.index_db)
    try:
        db.replace_all_symbols(conn, symbols)
        reindex(store, conn, _embedder_for(config))
    finally:
        conn.close()

    return {"modules": len({s.module for s in symbols}), "symbols": len(symbols)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_map_repo.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/operations.py tests/test_map_repo.py
git commit -m "feat: operations.map_repo (scan -> render -> store symbols -> index)"
```

---

### Task 6: `operations.get_intent`

**Files:**
- Modify: `src/torsor_helper/operations.py`
- Create: `tests/test_get_intent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_get_intent.py
from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _project(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_get_intent_returns_architecture(tmp_path):
    store = _project(tmp_path)
    out = ops.get_intent(store, TorsorConfig())
    assert "## System Patterns" in out
    assert "## Tech Context" in out
    assert "## Decisions" in out  # the seed ADR 0001


def test_get_intent_with_topic_surfaces_relevant_symbols(tmp_path):
    store = _project(tmp_path)
    (store.paths.root / "app.py").write_text("def format_date(d):\n    return d\n")
    ops.map_repo(store, TorsorConfig())
    out = ops.get_intent(store, TorsorConfig(), topic="format date")
    assert "Relevant existing symbols" in out
    assert "format_date(d)" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_get_intent.py -v`
Expected: FAIL — `AttributeError: module 'torsor_helper.operations' has no attribute 'get_intent'`

- [ ] **Step 3: Implement — append to `operations.py`**

```python
def get_intent(store: Store, config: TorsorConfig, topic: str | None = None) -> str:
    cpt = config.budgets.chars_per_token
    total = config.budgets.bootstrap_tokens
    sections: list[str] = []

    for label, path, frac in [
        ("System Patterns", store.paths.system_patterns, 0.4),
        ("Tech Context", store.paths.tech_context, 0.3),
    ]:
        if path.exists():
            note = store.read_note(path)
            text = truncate_to_tokens(note.body.strip(), int(total * frac), cpt)
            if text.strip():
                sections.append(f"## {label}\n\n{text}")

    if store.paths.decisions_dir.exists():
        titles = [store.read_note(p).title for p in sorted(store.paths.decisions_dir.glob("*.md"))]
        if titles:
            sections.append("## Decisions\n\n" + "\n".join(f"- {t}" for t in titles))

    if topic and store.paths.index_db.exists():
        conn = db.connect(store.paths.index_db)
        try:
            syms = db.search_symbols(conn, topic, limit=8)
        finally:
            conn.close()
        if syms:
            lines = [f"- `{s.signature}` ({s.kind}) — {s.module}:{s.line}" for s in syms]
            sections.append("## Relevant existing symbols\n\n" + "\n".join(lines))

    return "\n\n".join(sections)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_get_intent.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/operations.py tests/test_get_intent.py
git commit -m "feat: operations.get_intent (architecture + relevant symbols)"
```

---

### Task 7: MCP tools — `map_repo` + `get_intent`

**Files:**
- Modify: `src/torsor_helper/server.py`
- Create: `tests/test_server_map_intent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server_map_intent.py
import anyio

from torsor_helper.server import build_server


def test_server_registers_map_and_intent(tmp_path):
    server = build_server(tmp_path)
    tools = anyio.run(server.list_tools)
    names = {t.name for t in tools}
    assert {"map_repo", "get_intent"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_server_map_intent.py -v`
Expected: FAIL — assertion error (tools not registered)

- [ ] **Step 3: Implement — register both tools inside `build_server` in `server.py`** (alongside the others)

```python
    @mcp.tool()
    def map_repo(paths: list[str] | None = None) -> str:
        """(Re)generate the repository symbol map and refresh the symbol inventory."""
        stats = ops.map_repo(store, config, paths)
        return f"Mapped {stats['symbols']} symbol(s) across {stats['modules']} module(s)."

    @mcp.tool()
    def get_intent(topic: str = "") -> str:
        """Surface the architecture (patterns, tech, ADRs) and symbols relevant to a topic."""
        return ops.get_intent(store, config, topic or None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_server_map_intent.py -v`
Expected: PASS. Then `uv run --extra dev pytest -q` → full suite green (the existing `test_server.py` asserts a subset, so new tools don't break it).

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/server.py tests/test_server_map_intent.py
git commit -m "feat: map_repo + get_intent MCP tools"
```

---

### Task 8: CLI `torsor map`

**Files:**
- Modify: `src/torsor_helper/cli.py`
- Create: `tests/test_cli_map.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_map.py
from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.paths import TorsorPaths

runner = CliRunner()


def test_map_reports_counts_and_writes_overview(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "app.py").write_text("def run():\n    return 1\n")
    result = runner.invoke(app, ["map", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "mapped" in result.output.lower()
    assert TorsorPaths(tmp_path).map_overview.exists()


def test_map_requires_init(tmp_path):
    result = runner.invoke(app, ["map", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "not initialized" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_cli_map.py -v`
Expected: FAIL — no `map` command.

- [ ] **Step 3: Implement — add to `cli.py`**

Add the import (with the others): `from torsor_helper import operations as ops`. Add the command after `index`:
```python
@app.command()
def map(root: Path = typer.Option(Path("."), help="Project root to map.")) -> None:
    """Generate the repository symbol map under .torsor/map/."""
    paths = TorsorPaths(root)
    if not paths.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(paths)
    store = Store(paths)
    stats = ops.map_repo(store, config)
    typer.echo(f"Mapped {stats['symbols']} symbol(s) across {stats['modules']} module(s).")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_cli_map.py -v`
Expected: PASS (2 passed). Then full suite `uv run --extra dev pytest -q` green. Also smoke: `uv run torsor --help` lists `map`.

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/cli.py tests/test_cli_map.py
git commit -m "feat: torsor map CLI command"
```

---

### Task 9: Smoke (map torsor-helper itself) + README/roadmap sync

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Dogfood — map torsor-helper's own source**

```bash
cd /tmp && rm -rf th-map && cp -R /Users/magnetoid/Documents/trae_projects/torsor-mem th-map && cd th-map && rm -rf .torsor .venv
uv run --project /Users/magnetoid/Documents/trae_projects/torsor-mem torsor init
uv run --project /Users/magnetoid/Documents/trae_projects/torsor-mem torsor map
sed -n '1,40p' .torsor/map/overview.md
ls .torsor/map/modules/ | head
cd /tmp && rm -rf th-map
```
Expected: `map` reports a realistic count (dozens of symbols across the `torsor_helper` modules); `overview.md` lists `src/torsor_helper/*.py` modules with signatures; `modules/` has one file per module. No traceback.

- [ ] **Step 2: Tick the Phase 3 box + tool statuses in README**

In `README.md`: change the Phase 3 roadmap line to `- [x]`; in the MCP tools table move `get_intent` and `map_repo` to `✅ **shipped**`; update the badge to `Phase 3 shipped` and the test count.

```markdown
- [x] **Phase 3 — Map** · stdlib-`ast` cartographer + symbol inventory + `get_intent` / `map_repo` + `torsor map` *(shipped)*
```
Add a one-line note under "Built with" that the cartographer is Python-only today (multi-language via tree-sitter is planned).

- [ ] **Step 3: Run the full suite a final time**

Run: `uv run --extra dev pytest -q`
Expected: PASS (all green).

- [ ] **Step 4: Commit and push**

```bash
git add README.md
git commit -m "docs: mark Phase 3 (map) complete"
git push
```

---

## Self-Review

**Spec coverage** (Phase-3 scope from design spec §13 + Coach hooks §8):
- Cartographer / repo map → Tasks 1–3, 5 (stdlib `ast`, a documented refinement of "tree-sitter")
- Symbol graph / queryable inventory (Coach `reuse` hook) → Tasks 4–5 (`symbols` table + `search_symbols`)
- Module list (Coach `uncharted` hook) → Task 4 (`db.modules`)
- `get_intent` tool → Tasks 6–7
- `map_repo` tool → Tasks 5, 7
- `torsor map` CLI → Task 8
- Map Markdown committed + indexed → Task 5 (written via `store.write_note(type="map")`, reindexed)
- **Deferred (documented):** multi-language extraction via a pinned tree-sitter binding (Phase 3.x); PageRank-style ranking (current ranking is reference-count); ADR machine-rules + `check_drift` (Phase 4); the Coach's own logic (Phase 6).

**Placeholder scan:** none — every code/test step is runnable.

**Type consistency:** `Symbol` fields match across `models`/`cartographer`/`db`; `cartographer.{extract_symbols,iter_source_files,scan_repo,render_map}`, `db.{replace_all_symbols,search_symbols,modules}`, `operations.{map_repo,get_intent}` align with the locked contracts. `render_map` returns `{relpath: (title, body)}` consumed by `map_repo`. `SCHEMA_VERSION` bumped to 2; the existing `test_db.py` version assertion reads it dynamically.

## Notes for the implementer
- `ast` is stdlib — no new dependency. Keep `cartographer.py` pure (no MCP/CLI imports); `operations`/`server`/`cli` stay the adapters.
- `map_repo` rewrites `map/` wholesale and does a full `replace_all_symbols` each run — the map is a derived view, so this is intentional (no incremental complexity).
- `scan_repo`'s reference count is a cheap substring count (good enough for ranking + the Coach signal); a real call-graph is out of scope.
