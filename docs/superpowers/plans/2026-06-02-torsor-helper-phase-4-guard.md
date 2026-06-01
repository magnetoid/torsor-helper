# torsor-helper Phase 4 (Guard) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect drift from declared architectural intent — turn ADRs into machine-readable rules and flag changes that violate them — via `record_decision()` (write an ADR that carries rules) and `check_drift()` (verdict + citation), plus a `torsor guard` CLI.

**Architecture:** ADRs (and `system-patterns.md`) carry a `rules:` list in their YAML frontmatter. A pure `guard` module loads those rules and checks source files against them with two deterministic checkers — `forbid_import` (stdlib `ast`) and `forbid_pattern` (regex) — producing `Violation` records that cite the ADR that declared the rule. `operations`/`server`/`cli` stay thin. The guard is **advisory** (never blocks an edit); `torsor guard --strict` exits non-zero for CI use.

**Tech Stack:** Python ≥3.11 stdlib (`ast`, `re`, `fnmatch`, `subprocess` for git-changed files); builds on Phase-1/3 `store`/`models`/`operations`/`config`.

**Key design decision — deterministic guard now, sampling-based semantic guard deferred:** the design spec's two-layer drift detection includes an MCP-**sampling** semantic check ("ask the host model if this diff violates intent"). Sampling support is client-dependent and its API can't be reliably probed or unit-tested in a headless environment, and it's non-deterministic. So Phase 4 ships the **deterministic** layer in full (rules from ADRs → AST/regex checks → cited verdict) — the testable core of the differentiator — and leaves a clean seam for the semantic layer as a documented fast-follow. This mirrors the Phase-2 (BLOB+NumPy over sqlite-vec) and Phase-3 (ast over tree-sitter) pragmatic calls.

---

## File Structure

```
src/torsor_helper/models.py       # MODIFY: add Rule, Violation
src/torsor_helper/guard.py        # load_rules + forbid_import/forbid_pattern checks + check_drift
src/torsor_helper/operations.py   # MODIFY: add record_decision() and check_drift()
src/torsor_helper/server.py       # MODIFY: register record_decision + check_drift tools
src/torsor_helper/cli.py          # MODIFY: add `torsor guard`
tests/test_guard_rules.py
tests/test_guard_checks.py
tests/test_record_decision.py
tests/test_check_drift.py
tests/test_server_guard.py
tests/test_cli_guard.py
```

## Interface contracts (locked — use these exact names)

- `models.Rule(BaseModel)`: `kind:str` ("forbid_import"|"forbid_pattern"), `target:str`, `scope:str="*.py"`, `message:str=""`, `source:str=""`.
- `models.Violation(BaseModel)`: `rule_kind:str`, `target:str`, `file:str`, `line:int=0`, `message:str`, `source:str`.
- `guard.load_rules(store) -> list[Rule]`; `guard.violations_for_file(relpath:str, text:str, rule:Rule) -> list[Violation]`; `guard.check_drift(store, files) -> list[Violation]`.
- `operations.record_decision(store, title, context, decision, consequences="", rules=None) -> str` (returns ADR path); `operations.check_drift(store, config, files=None) -> list[Violation]`.
- `server` tools: `record_decision(title, context, decision, consequences="", rules=None) -> str`, `check_drift(files: list[str] | None = None) -> str`.

---

### Task 1: Rule + Violation models + `guard.load_rules`

**Files:**
- Modify: `src/torsor_helper/models.py`
- Create: `src/torsor_helper/guard.py`
- Create: `tests/test_guard_rules.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guard_rules.py
from datetime import datetime

from torsor_helper.guard import load_rules
from torsor_helper.models import Rule
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_load_rules_reads_adr_frontmatter(tmp_path):
    store = _store(tmp_path)
    adr = store.paths.decisions_dir / "0002-no-requests-in-domain.md"
    adr.write_text(
        "---\n"
        "type: decision\n"
        "status: accepted\n"
        "rules:\n"
        "  - kind: forbid_import\n"
        "    target: requests\n"
        "    scope: 'domain/*.py'\n"
        "    message: domain must stay framework-free\n"
        "---\n\n# ADR 0002: No requests in domain\n\nbody\n"
    )
    rules = load_rules(store)
    assert any(r.kind == "forbid_import" and r.target == "requests" for r in rules)
    rule = next(r for r in rules if r.target == "requests")
    assert rule.scope == "domain/*.py"
    assert rule.source  # the ADR title is attached for citation
    assert isinstance(rule, Rule)


def test_load_rules_skips_malformed(tmp_path):
    store = _store(tmp_path)
    adr = store.paths.decisions_dir / "0003-bad.md"
    adr.write_text("---\ntype: decision\nrules:\n  - notakey: x\n---\n\n# ADR 0003: Bad\n\nb\n")
    # malformed rule (missing kind/target) is skipped, not fatal
    rules = load_rules(store)
    assert all(r.source != "ADR 0003: Bad" for r in rules)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_guard_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.guard'`

- [ ] **Step 3: Implement**

Add to `src/torsor_helper/models.py` (after `Symbol`):
```python
class Rule(BaseModel):
    kind: str            # "forbid_import" | "forbid_pattern"
    target: str          # module prefix (forbid_import) or regex (forbid_pattern)
    scope: str = "*.py"  # fnmatch glob over the posix path, relative to the repo root
    message: str = ""
    source: str = ""     # ADR/title that declared this rule (for citation)


class Violation(BaseModel):
    rule_kind: str
    target: str
    file: str
    line: int = 0
    message: str
    source: str
```

Create `src/torsor_helper/guard.py`:
```python
from __future__ import annotations

from torsor_helper.models import Rule, Violation
from torsor_helper.store import Store

_RULE_SOURCES = ("decisions", "system_patterns")


def load_rules(store: Store) -> list[Rule]:
    notes = []
    if store.paths.decisions_dir.exists():
        notes.extend(sorted(store.paths.decisions_dir.glob("*.md")))
    if store.paths.system_patterns.exists():
        notes.append(store.paths.system_patterns)

    rules: list[Rule] = []
    for path in notes:
        note = store.read_note(path)
        raw = getattr(note.frontmatter, "rules", None)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                rule = Rule.model_validate({**item, "source": note.title})
            except Exception:
                continue  # malformed rule: skip, never fatal
            rules.append(rule)
    return rules
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_guard_rules.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/models.py src/torsor_helper/guard.py tests/test_guard_rules.py
git commit -m "feat: Rule/Violation models + guard.load_rules from ADR frontmatter"
```

---

### Task 2: Deterministic checks + `guard.check_drift`

**Files:**
- Modify: `src/torsor_helper/guard.py`
- Create: `tests/test_guard_checks.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guard_checks.py
from datetime import datetime

from torsor_helper.guard import check_drift, violations_for_file
from torsor_helper.models import Rule
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def test_forbid_import_flags_matching_import():
    rule = Rule(kind="forbid_import", target="requests", scope="*.py", message="no requests", source="ADR 2")
    text = "import os\nimport requests\nfrom requests.sessions import Session\n"
    vs = violations_for_file("app.py", text, rule)
    assert len(vs) == 2
    assert vs[0].line == 2 and vs[0].file == "app.py" and vs[0].source == "ADR 2"


def test_forbid_import_ignores_unrelated_and_syntax_errors():
    rule = Rule(kind="forbid_import", target="requests", source="ADR 2")
    assert violations_for_file("a.py", "import os\nfrom json import loads\n", rule) == []
    assert violations_for_file("a.py", "def broken(:\n", rule) == []  # syntax error -> no crash


def test_forbid_pattern_flags_regex_per_line():
    rule = Rule(kind="forbid_pattern", target=r"TODO|FIXME", scope="*.py", message="no TODOs", source="ADR 5")
    text = "x = 1\n# TODO: later\ny = 2  # FIXME\n"
    vs = violations_for_file("a.py", text, rule)
    assert {v.line for v in vs} == {2, 3}


def test_check_drift_applies_scoped_rules(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    adr = store.paths.decisions_dir / "0002-no-requests-in-domain.md"
    adr.write_text(
        "---\ntype: decision\nrules:\n  - kind: forbid_import\n    target: requests\n    scope: 'domain/*.py'\n---\n\n# ADR 0002: x\n\nb\n"
    )
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    (tmp_path / "infra.py").write_text("import requests\n")  # out of scope
    vs = check_drift(store, ["domain/svc.py", "infra.py"])
    files = {v.file for v in vs}
    assert "domain/svc.py" in files
    assert "infra.py" not in files  # scope is domain/*.py only
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_guard_checks.py -v`
Expected: FAIL — `ImportError: cannot import name 'violations_for_file'`

- [ ] **Step 3: Implement — add to `guard.py`** (add the imports at the top)

At the top of `guard.py`:
```python
import ast
import fnmatch
import re
from pathlib import Path
```
Append:
```python
def _forbid_import(relpath: str, text: str, rule: Rule) -> list[Violation]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    target = rule.target
    out: list[Violation] = []

    def hit(name: str | None) -> bool:
        return bool(name) and (name == target or name.startswith(target + "."))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if hit(alias.name):
                    out.append(_violation(rule, relpath, node.lineno, f"imports forbidden module '{alias.name}'"))
        elif isinstance(node, ast.ImportFrom):
            if hit(node.module):
                out.append(_violation(rule, relpath, node.lineno, f"imports from forbidden module '{node.module}'"))
    return out


def _forbid_pattern(relpath: str, text: str, rule: Rule) -> list[Violation]:
    try:
        pattern = re.compile(rule.target)
    except re.error:
        return []
    out: list[Violation] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            out.append(_violation(rule, relpath, i, f"matches forbidden pattern '{rule.target}'"))
    return out


def _violation(rule: Rule, relpath: str, line: int, default_msg: str) -> Violation:
    return Violation(
        rule_kind=rule.kind, target=rule.target, file=relpath, line=line,
        message=rule.message or default_msg, source=rule.source,
    )


_CHECKERS = {"forbid_import": _forbid_import, "forbid_pattern": _forbid_pattern}


def violations_for_file(relpath: str, text: str, rule: Rule) -> list[Violation]:
    checker = _CHECKERS.get(rule.kind)
    if checker is None:
        return []
    return checker(relpath, text, rule)


def check_drift(store: Store, files) -> list[Violation]:
    rules = load_rules(store)
    if not rules:
        return []
    root = store.paths.root
    out: list[Violation] = []
    for raw in files:
        path = Path(raw)
        abs_path = path if path.is_absolute() else root / path
        try:
            text = abs_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            relpath = abs_path.relative_to(root).as_posix()
        except ValueError:
            relpath = abs_path.name
        for rule in rules:
            if fnmatch.fnmatch(relpath, rule.scope):
                out.extend(violations_for_file(relpath, text, rule))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_guard_checks.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/guard.py tests/test_guard_checks.py
git commit -m "feat: forbid_import (ast) + forbid_pattern (regex) checks + check_drift"
```

---

### Task 3: `operations.record_decision`

**Files:**
- Modify: `src/torsor_helper/operations.py`
- Create: `tests/test_record_decision.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_record_decision.py
from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.guard import load_rules
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_record_decision_numbers_and_writes_adr(tmp_path):
    store = _store(tmp_path)
    # seed scaffold already wrote 0001; next is 0002
    path = ops.record_decision(
        store, title="Use SQLite for the index",
        context="We need local-first storage.", decision="Adopt SQLite.",
        consequences="No server to run.",
    )
    assert path.endswith("0002-use-sqlite-for-the-index.md")
    text = (store.paths.decisions_dir / "0002-use-sqlite-for-the-index.md").read_text()
    assert "# ADR 0002: Use SQLite for the index" in text
    assert "## Decision" in text and "Adopt SQLite." in text


def test_record_decision_rules_become_loadable(tmp_path):
    store = _store(tmp_path)
    ops.record_decision(
        store, title="No requests in domain", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "domain/*.py"}],
    )
    rules = load_rules(store)
    assert any(r.target == "requests" and r.kind == "forbid_import" for r in rules)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_record_decision.py -v`
Expected: FAIL — `AttributeError: module 'torsor_helper.operations' has no attribute 'record_decision'`

- [ ] **Step 3: Implement — append to `operations.py`** (add `import re` at the top if not present)

```python
import re as _re  # for slugging (avoid clobbering any existing re import)


def _next_adr_number(store) -> int:
    nums = []
    if store.paths.decisions_dir.exists():
        for p in store.paths.decisions_dir.glob("*.md"):
            m = _re.match(r"(\d+)", p.name)
            if m:
                nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def _slug(title: str) -> str:
    s = _re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s or "decision"


def record_decision(store, title, context, decision, consequences="", rules=None) -> str:
    number = _next_adr_number(store)
    fm = Frontmatter(type="decision", status="accepted", tags=["adr"], rules=rules or [])
    body = (
        f"## Context\n{context}\n\n"
        f"## Decision\n{decision}\n\n"
        f"## Consequences\n{consequences}\n"
    )
    target = store.paths.decisions_dir / f"{number:04d}-{_slug(title)}.md"
    store.write_note(target, fm, f"ADR {number:04d}: {title}", body)
    return str(target)
```

> Note: `Frontmatter(..., rules=...)` works because `Frontmatter` has `extra="allow"` (Phase 1). The `rules` list round-trips through `serialize`/`parse_frontmatter` as YAML.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_record_decision.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/operations.py tests/test_record_decision.py
git commit -m "feat: operations.record_decision (numbered ADR with rules)"
```

---

### Task 4: `operations.check_drift` (+ git-changed fallback)

**Files:**
- Modify: `src/torsor_helper/operations.py`
- Create: `tests/test_check_drift.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_check_drift.py
from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _project_with_rule(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    ops.record_decision(
        store, title="No requests in domain", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "domain/*.py"}],
    )
    return store


def test_check_drift_flags_violation_with_explicit_files(tmp_path):
    store = _project_with_rule(tmp_path)
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    violations = ops.check_drift(store, TorsorConfig(), files=["domain/svc.py"])
    assert len(violations) == 1
    assert violations[0].file == "domain/svc.py"
    assert "No requests in domain" in violations[0].source


def test_check_drift_clean_when_no_violation(tmp_path):
    store = _project_with_rule(tmp_path)
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain" / "ok.py").write_text("import os\n")
    assert ops.check_drift(store, TorsorConfig(), files=["domain/ok.py"]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_check_drift.py -v`
Expected: FAIL — `AttributeError: module 'torsor_helper.operations' has no attribute 'check_drift'`

- [ ] **Step 3: Implement — append to `operations.py`** (add `import subprocess` at top if not present, and `from torsor_helper import guard`)

```python
def _git_changed(root) -> list[str]:
    import subprocess
    try:
        changed = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.split()
        untracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, timeout=10,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return []
    return [f for f in (changed + untracked) if f.endswith(".py")]


def check_drift(store, config, files=None) -> list:
    if files is None:
        files = _git_changed(store.paths.root)
    return guard.check_drift(store, files)
```

Add `from torsor_helper import guard` to the existing `from torsor_helper import ...` import line.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_check_drift.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/operations.py tests/test_check_drift.py
git commit -m "feat: operations.check_drift with git-changed fallback"
```

---

### Task 5: MCP tools — `record_decision` + `check_drift`

**Files:**
- Modify: `src/torsor_helper/server.py`
- Create: `tests/test_server_guard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server_guard.py
import anyio

from torsor_helper.server import build_server


def test_server_registers_guard_tools(tmp_path):
    server = build_server(tmp_path)
    tools = anyio.run(server.list_tools)
    names = {t.name for t in tools}
    assert {"record_decision", "check_drift"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_server_guard.py -v`
Expected: FAIL — assertion error (tools missing)

- [ ] **Step 3: Implement — register inside `build_server` in `server.py`**

```python
    @mcp.tool()
    def record_decision(title: str, context: str, decision: str, consequences: str = "", rules: list[dict] | None = None) -> str:
        """Record an Architecture Decision Record. Optional `rules` become drift-guard rules."""
        path = ops.record_decision(store, title, context, decision, consequences, rules)
        return f"Recorded {path}"

    @mcp.tool()
    def check_drift(files: list[str] | None = None) -> str:
        """Flag changes that violate declared architectural intent (ADR rules). Defaults to git-changed files."""
        violations = ops.check_drift(store, config, files)
        if not violations:
            return "No drift from declared intent detected."
        lines = [f"- {v.file}:{v.line} — {v.message} (per {v.source})" for v in violations]
        return f"{len(violations)} drift violation(s):\n" + "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_server_guard.py -v`
Expected: PASS. Then `uv run --extra dev pytest -q` → full suite green (existing `test_server.py` asserts a subset).

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/server.py tests/test_server_guard.py
git commit -m "feat: record_decision + check_drift MCP tools"
```

---

### Task 6: CLI `torsor guard`

**Files:**
- Modify: `src/torsor_helper/cli.py`
- Create: `tests/test_cli_guard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_guard.py
from datetime import datetime

from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.config import load_config
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def _seed(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    store = Store(TorsorPaths(tmp_path), clock=lambda: datetime(2026, 6, 2, 9, 0, 0))
    ops.record_decision(
        store, title="No requests in domain", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "domain/*.py"}],
    )
    (tmp_path / "domain").mkdir()


def test_guard_reports_violation_for_explicit_file(tmp_path):
    _seed(tmp_path)
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    result = runner.invoke(app, ["guard", "--root", str(tmp_path), "domain/svc.py"])
    assert result.exit_code == 0  # advisory by default
    assert "violation" in result.output.lower()


def test_guard_strict_exits_nonzero_on_violation(tmp_path):
    _seed(tmp_path)
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    result = runner.invoke(app, ["guard", "--root", str(tmp_path), "--strict", "domain/svc.py"])
    assert result.exit_code == 1


def test_guard_clean_reports_no_drift(tmp_path):
    _seed(tmp_path)
    (tmp_path / "domain" / "ok.py").write_text("import os\n")
    result = runner.invoke(app, ["guard", "--root", str(tmp_path), "domain/ok.py"])
    assert result.exit_code == 0
    assert "no drift" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_cli_guard.py -v`
Expected: FAIL — no `guard` command.

- [ ] **Step 3: Implement — add to `cli.py`** (uses `ops`, `load_config`, `Store`, `TorsorPaths` already imported)

```python
@app.command()
def guard(
    paths: list[str] = typer.Argument(None, help="Files to check (default: git-changed .py files)."),
    root: Path = typer.Option(Path("."), help="Project root."),
    strict: bool = typer.Option(False, help="Exit non-zero if any violation is found (for CI)."),
) -> None:
    """Check changes against declared architectural intent (ADR rules)."""
    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(tp)
    store = Store(tp)
    violations = ops.check_drift(store, config, paths or None)
    if not violations:
        typer.echo("No drift from declared intent detected.")
        return
    for v in violations:
        typer.echo(f"{v.file}:{v.line} — {v.message} (per {v.source})")
    typer.echo(f"\n{len(violations)} drift violation(s).")
    if strict:
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_cli_guard.py -v`
Expected: PASS (3 passed). Then `uv run --extra dev pytest -q` → full suite green. Smoke: `uv run torsor --help` lists `guard`.

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/cli.py tests/test_cli_guard.py
git commit -m "feat: torsor guard CLI (advisory; --strict for CI)"
```

---

### Task 7: Dogfood smoke + README/roadmap sync

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Dogfood — add a real rule and prove the guard fires**

```bash
cd /tmp && rm -rf thguard && mkdir thguard && cd thguard
uv run --project /Users/magnetoid/Documents/trae_projects/torsor-mem torsor init >/dev/null
# add an ADR rule: forbid importing 'os' anywhere (just to prove the mechanism), then a violating file
python3 - <<'PY'
from pathlib import Path
adr = Path(".torsor/architecture/decisions/0002-no-os.md")
adr.write_text("---\ntype: decision\nrules:\n  - kind: forbid_import\n    target: os\n    scope: '*.py'\n    message: demo rule\n---\n\n# ADR 0002: demo\n\nbody\n")
Path("bad.py").write_text("import os\n")
PY
uv run --project /Users/magnetoid/Documents/trae_projects/torsor-mem torsor guard bad.py
echo "exit: $?"
uv run --project /Users/magnetoid/Documents/trae_projects/torsor-mem torsor guard --strict bad.py; echo "strict exit: $?"
cd /tmp && rm -rf thguard
```
Expected: the first `guard` lists `bad.py:1 — demo rule (per ADR 0002: demo)` and prints `exit: 0` (advisory); the `--strict` run prints `strict exit: 1`. No traceback.

- [ ] **Step 2: Tick the Phase 4 box + tool statuses in README**

In `README.md`: change the Phase 4 roadmap line to `- [x]`; move `record_decision` / `check_drift` in the MCP tools table to `✅ **shipped**`; update the status badge to `Phase 4 shipped` and the test count. Note in "Built with" that drift detection is deterministic (ADR rules; the sampling-based semantic guard is a planned fast-follow).

```markdown
- [x] **Phase 4 — Guard** · ADR rules + deterministic drift detection (`record_decision` / `check_drift`) + `torsor guard` *(shipped)*
```

- [ ] **Step 3: Run the full suite a final time**

Run: `uv run --extra dev pytest -q`
Expected: PASS (all green).

- [ ] **Step 4: Commit and push**

```bash
git add README.md
git commit -m "docs: mark Phase 4 (guard) complete"
git push
```

---

## Self-Review

**Spec coverage** (Phase-4 scope from design spec §8 + §13 + Coach hook §8):
- ADRs carry machine-readable `rules:` → Tasks 1, 3
- Deterministic guard (AST `forbid_import` + regex `forbid_pattern`) → Task 2
- `record_decision` tool/op → Tasks 3, 5
- `check_drift` tool/op (verdict + citation of the violated ADR) → Tasks 2, 4, 5
- `torsor guard` CLI (advisory; `--strict` for CI) → Task 6
- Coach hook: ADR `rules:` are the shared rules source (`guard.load_rules`) the Phase-6 Coach uses for `convention`/`unruled` → Tasks 1–2
- **Deferred (documented):** the MCP-**sampling** semantic guard — client-dependent API, non-deterministic, can't be reliably tested headless; ships as a fast-follow with `check_drift` already returning a structured/cited result that a semantic layer can extend. Out-of-scope here per the plan's key design decision.

**Placeholder scan:** none — every code/test step is runnable.

**Type consistency:** `Rule`/`Violation` fields match across `models`/`guard`/`operations`; `guard.{load_rules,violations_for_file,check_drift}`, `operations.{record_decision,check_drift}` align with the locked contracts. `Frontmatter(rules=...)` relies on Phase-1 `extra="allow"`. `check_drift` returns `list[Violation]`; server/cli format it.

## Notes for the implementer
- Keep `guard.py` pure (stdlib only: `ast`/`re`/`fnmatch`/`pathlib`); `operations`/`server`/`cli` stay adapters. `_git_changed` is the only subprocess use and is wrapped so a non-git or git-less environment degrades to an empty list (→ "no drift").
- Rule `scope` uses `fnmatch` over the posix relpath: `*` matches across `/` (fnmatch semantics). Default `*.py`. Document this if a rule needs directory precision.
- The guard is advisory by contract — only `torsor guard --strict` (CI) exits non-zero. The MCP `check_drift` tool never raises; it returns a verdict string.