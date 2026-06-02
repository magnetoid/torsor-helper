# torsor-helper Phase 5 (Consolidation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make memory self-improving — mine raw journal entries into curated, indexed *insight notes*, surface duplicates and the most-recalled notes, all via a `torsor consolidate` maintenance pass (also exposed as a `consolidate` MCP tool).

**Architecture:** A pure `coach/mining.py` parses journal entries (`## HH:MM · kind` sections), aggregates `learning`/`decision`/`rejection`/`blocker` entries by kind, and writes idempotent insight notes under `memory/insights/` (which then index like any note and enrich the Coach's recs). `operations.consolidate` orchestrates: mine → reindex → report duplicate entries + most-recalled notes (from the index's `access_count`). `cli`/`server` are thin adapters. Markdown stays the source of truth; nothing is deleted — consolidation only *adds* derived insights and *reports*.

**Tech Stack:** Python ≥3.11 stdlib (`re`); builds on shipped `store`/`models`/`db`/`coach`/`operations`/`config`.

**Deferred (documented fast-follows):** HTTP/team transport (`torsor mcp --http`) — FastMCP's transport API is version-dependent and not safely unit-testable headless, same reasoning as the deferred sampling guard; auto-pruning of stale notes (consolidation *reports* staleness via the Coach's `uncharted`/access data but never deletes source Markdown, by the "Markdown is truth" principle).

---

## File Structure

```
src/torsor_helper/coach/mining.py   # parse_journal_entries + mine_insights + find_duplicate_entries (pure)
src/torsor_helper/db.py             # MODIFY: add top_accessed()
src/torsor_helper/operations.py     # MODIFY: add consolidate()
src/torsor_helper/cli.py            # MODIFY: add `torsor consolidate`
src/torsor_helper/server.py         # MODIFY: add `consolidate` MCP tool
tests/test_coach_mining.py
tests/test_db_top_accessed.py
tests/test_consolidate_op.py
tests/test_cli_consolidate.py
```

## Interface contracts (locked — use these exact names)

- `coach.mining.parse_journal_entries(body:str) -> list[tuple[str,str]]` (kind, content; excludes the `Links:` line).
- `coach.mining.mine_insights(store) -> list[Path]` (writes/refreshes `insights/<kind>.md` for mined kinds; returns written paths).
- `coach.mining.find_duplicate_entries(store) -> list[tuple[str,int]]` (content, count) for entries appearing >1, sorted by count desc then content.
- `db.top_accessed(conn, limit=5) -> list[tuple[str,int]]` (path, access_count) where access_count > 0, ordered desc.
- `operations.consolidate(store, config) -> dict` (`{"insights","duplicates","indexed"}`).

---

### Task 1: Journal mining (`coach/mining.py`)

**Files:**
- Create: `src/torsor_helper/coach/mining.py`
- Create: `tests/test_coach_mining.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_coach_mining.py
from datetime import datetime

from torsor_helper.coach import mining
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_parse_journal_entries_splits_by_kind():
    body = (
        "## 09:00 · learning\n\nprefer uv run over pip\n\nLinks: [[charter]]\n"
        "## 10:00 · decision\n\nchose SQLite\n"
    )
    entries = mining.parse_journal_entries(body)
    assert ("learning", "prefer uv run over pip") in entries
    assert ("decision", "chose SQLite") in entries
    # the Links: line is excluded from content
    assert all("Links:" not in c for _, c in entries)


def test_mine_insights_writes_per_kind_notes(tmp_path):
    store = _store(tmp_path)
    store.append_journal("prefer uv run over pip", kind="learning", links=[])
    store.append_journal("always TDD", kind="learning", links=[])
    store.append_journal("avoid global state", kind="rejection", links=[])
    written = mining.mine_insights(store)
    names = {p.name for p in written}
    assert "learning.md" in names and "rejection.md" in names
    learning_md = (store.paths.insights_dir / "learning.md").read_text()
    assert "prefer uv run over pip" in learning_md and "always TDD" in learning_md


def test_mine_insights_is_idempotent(tmp_path):
    store = _store(tmp_path)
    store.append_journal("only once", kind="learning", links=[])
    mining.mine_insights(store)
    mining.mine_insights(store)  # second run must not duplicate the bullet
    text = (store.paths.insights_dir / "learning.md").read_text()
    assert text.count("only once") == 1


def test_find_duplicate_entries(tmp_path):
    store = _store(tmp_path)
    store.append_journal("dup note", kind="observation", links=[])
    store.append_journal("dup note", kind="observation", links=[])
    store.append_journal("unique", kind="observation", links=[])
    dups = mining.find_duplicate_entries(store)
    assert ("dup note", 2) in dups
    assert all(c != "unique" for c, _ in dups)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_coach_mining.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.coach.mining'`

- [ ] **Step 3: Implement** — `src/torsor_helper/coach/mining.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

from torsor_helper.models import Frontmatter
from torsor_helper.store import Store

# Journal entries are written by store.append_journal as:  "## HH:MM · <kind>\n\n<content>\n"
_ENTRY = re.compile(r"^## \d{2}:\d{2} · (\S+)\n(.*?)(?=^## \d{2}:\d{2} ·|\Z)", re.MULTILINE | re.DOTALL)
_MINED_KINDS = ("learning", "decision", "rejection", "blocker")


def parse_journal_entries(body: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for match in _ENTRY.finditer(body):
        kind = match.group(1)
        lines = [ln for ln in match.group(2).splitlines() if not ln.startswith("Links:")]
        content = "\n".join(lines).strip()
        if content:
            out.append((kind, content))
    return out


def _all_entries(store: Store) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if store.paths.journal_dir.exists():
        for jpath in sorted(store.paths.journal_dir.glob("*.md")):
            out.extend(parse_journal_entries(store.read_note(jpath).body))
    return out


def mine_insights(store: Store) -> list[Path]:
    by_kind: dict[str, list[str]] = {}
    for kind, content in _all_entries(store):
        if kind in _MINED_KINDS:
            by_kind.setdefault(kind, []).append(content)

    store.paths.insights_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for kind, items in by_kind.items():
        seen: set[str] = set()
        uniq = [it for it in items if not (it in seen or seen.add(it))]
        body = "\n".join(f"- {it}" for it in uniq)
        target = store.paths.insights_dir / f"{kind}.md"
        store.write_note(target, Frontmatter(type="insight", tags=["insight"], kind=kind), f"Mined {kind}s", body)
        written.append(target)
    return written


def find_duplicate_entries(store: Store) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for _kind, content in _all_entries(store):
        counts[content] = counts.get(content, 0) + 1
    dups = [(content, n) for content, n in counts.items() if n > 1]
    dups.sort(key=lambda t: (-t[1], t[0]))
    return dups
```

> Note: `Frontmatter(type="insight", ..., kind=kind)` relies on Phase-1 `extra="allow"`; the indexer reads `getattr(frontmatter, "kind", None)` so mined insights are `kind`-filterable. Insight notes live under `memory/insights/` (EPISODIC tier), so the Coach's recommender surfaces them as `learning` recs. The `not (it in seen or seen.add(it))` idiom dedupes while preserving order (`set.add` returns None → falsy).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_coach_mining.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/coach/mining.py tests/test_coach_mining.py
git commit -m "feat: journal mining (insights per kind + duplicate detection)"
```

---

### Task 2: `db.top_accessed`

**Files:**
- Modify: `src/torsor_helper/db.py`
- Create: `tests/test_db_top_accessed.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db_top_accessed.py
from torsor_helper import db


def test_top_accessed_orders_by_count_excludes_zero(tmp_path):
    conn = db.connect(tmp_path / "torsor.db")
    for path in ("a.md", "b.md", "c.md"):
        db.upsert_note(conn, path, "h", 4, "journal", None, path, "t")
    db.bump_access(conn, ["a.md", "a.md", "a.md"])  # a -> 3
    db.bump_access(conn, ["b.md"])                   # b -> 1
    top = db.top_accessed(conn, limit=5)
    assert top[0] == ("a.md", 3)
    assert ("b.md", 1) in top
    assert all(p != "c.md" for p, _ in top)  # c never accessed -> excluded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_db_top_accessed.py -v`
Expected: FAIL — `AttributeError: module 'torsor_helper.db' has no attribute 'top_accessed'`

- [ ] **Step 3: Implement** — append to `db.py`:

```python
def top_accessed(conn, limit=5):
    rows = conn.execute(
        "SELECT path, access_count FROM notes WHERE access_count > 0 "
        "ORDER BY access_count DESC, path LIMIT ?",
        (limit,),
    ).fetchall()
    return [(r["path"], r["access_count"]) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_db_top_accessed.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/db.py tests/test_db_top_accessed.py
git commit -m "feat: db.top_accessed (most-recalled notes)"
```

---

### Task 3: `operations.consolidate`

**Files:**
- Modify: `src/torsor_helper/operations.py`
- Create: `tests/test_consolidate_op.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_consolidate_op.py
from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_consolidate_mines_and_reports(tmp_path):
    store = _store(tmp_path)
    store.append_journal("prefer uv run", kind="learning", links=[])
    store.append_journal("dup", kind="observation", links=[])
    store.append_journal("dup", kind="observation", links=[])
    stats = ops.consolidate(store, TorsorConfig())
    assert stats["insights"] >= 1                 # learning.md written
    assert stats["duplicates"] >= 1               # the "dup" pair
    assert (store.paths.insights_dir / "learning.md").exists()


def test_consolidate_insight_is_recallable(tmp_path):
    store = _store(tmp_path)
    store.append_journal("cache the embedder per process", kind="learning", links=[])
    ops.consolidate(store, TorsorConfig())
    # the mined insight is indexed -> recall finds it
    res = ops.recall(store, TorsorConfig(), "embedder cache")
    assert any("embedder" in h.snippet for h in res.hits)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_consolidate_op.py -v`
Expected: FAIL — `AttributeError: module 'torsor_helper.operations' has no attribute 'consolidate'`

- [ ] **Step 3: Implement** — append to `operations.py` (add `from torsor_helper.coach import mining as coach_mining` to the imports):

```python
def consolidate(store, config) -> dict:
    written = coach_mining.mine_insights(store)
    duplicates = coach_mining.find_duplicate_entries(store)

    indexed = 0
    conn = _open_index(store, config)
    if conn is not None:
        try:
            indexed = reindex(store, conn, _embedder_for(config))["indexed"]
        finally:
            conn.close()

    return {"insights": len(written), "duplicates": len(duplicates), "indexed": indexed}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_consolidate_op.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full suite**

Run: `uv run --extra dev pytest -q`
Expected: PASS (all green).

- [ ] **Step 6: Commit**

```bash
git add src/torsor_helper/operations.py tests/test_consolidate_op.py
git commit -m "feat: operations.consolidate (mine insights + reindex + report)"
```

---

### Task 4: `torsor consolidate` CLI + `consolidate` MCP tool

**Files:**
- Modify: `src/torsor_helper/cli.py`
- Modify: `src/torsor_helper/server.py`
- Create: `tests/test_cli_consolidate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_consolidate.py
import anyio
from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.server import build_server

runner = CliRunner()


def test_consolidate_cli_reports_counts(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["consolidate", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "insight" in result.output.lower()


def test_consolidate_requires_init(tmp_path):
    result = runner.invoke(app, ["consolidate", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "not initialized" in result.output.lower()


def test_server_registers_consolidate_tool(tmp_path):
    server = build_server(tmp_path)
    names = {t.name for t in anyio.run(server.list_tools)}
    assert "consolidate" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_cli_consolidate.py -v`
Expected: FAIL — no `consolidate` command/tool.

- [ ] **Step 3: Implement**

In `cli.py`, add after the `coach` command:
```python
@app.command()
def consolidate(root: Path = typer.Option(Path("."), help="Project root.")) -> None:
    """Self-improving maintenance: mine journal insights, reindex, report duplicates."""
    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(tp)
    store = Store(tp)
    stats = ops.consolidate(store, config)
    typer.echo(
        f"Mined {stats['insights']} insight file(s); reindexed {stats['indexed']} note(s); "
        f"found {stats['duplicates']} duplicate entr(y/ies)."
    )
```

In `server.py`, register inside `build_server` (alongside the other tools):
```python
    @mcp.tool()
    def consolidate() -> str:
        """Self-improving maintenance: mine journal entries into insight notes, reindex, report duplicates."""
        stats = ops.consolidate(store, config)
        return (
            f"Mined {stats['insights']} insight file(s); reindexed {stats['indexed']} note(s); "
            f"found {stats['duplicates']} duplicate entr(y/ies)."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_cli_consolidate.py -v`
Expected: PASS (3 passed). Then `uv run --extra dev pytest -q` → full suite green. Smoke: `uv run torsor --help` lists `consolidate`.

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/cli.py src/torsor_helper/server.py tests/test_cli_consolidate.py
git commit -m "feat: torsor consolidate CLI + consolidate MCP tool"
```

---

### Task 5: Dogfood smoke + README/CHANGELOG sync + self-review

**Files:**
- Modify: `README.md`, `CHANGELOG.md`

- [ ] **Step 1: Dogfood — consolidate on a project with real journal entries**

```bash
cd /tmp && rm -rf thcons && mkdir thcons && cd thcons
uv run --project /Users/magnetoid/Documents/trae_projects/torsor-mem torsor init >/dev/null
uv run --project /Users/magnetoid/Documents/trae_projects/torsor-mem python - <<'PY'
from datetime import datetime
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store
s = Store(TorsorPaths("."), clock=datetime.now)
s.append_journal("prefer uv run over pip", kind="learning", links=[])
s.append_journal("chose RRF for fusion", kind="decision", links=[])
s.append_journal("prefer uv run over pip", kind="learning", links=[])  # duplicate
print("seeded journal")
PY
uv run --project /Users/magnetoid/Documents/trae_projects/torsor-mem torsor consolidate 2>&1 | grep -iv warning
echo "--- mined insight files ---" && ls .torsor/memory/insights/ && cat .torsor/memory/insights/learning.md
cd /tmp && rm -rf thcons
```
Expected: `consolidate` reports ≥2 insight files, ≥1 duplicate; `memory/insights/learning.md` lists "prefer uv run over pip" once (deduped). No traceback.

- [ ] **Step 2: Update README + CHANGELOG**

In `README.md`: tick the Phase 5 roadmap box; add a `consolidate` tool/command mention; bump the status badge + test count. Note HTTP/team transport remains a planned fast-follow.

```markdown
- [x] **Phase 5 — Consolidation** · `torsor consolidate` mines journal entries into curated insight notes + reindexes + reports duplicates *(shipped)*
```

In `CHANGELOG.md`: add a "Phase 5 — Consolidation" section (journal mining into per-kind insight notes that feed the Coach; duplicate detection; `db.top_accessed`; `torsor consolidate` CLI + MCP tool; HTTP/team transport and auto-pruning deferred).

- [ ] **Step 3: Run the full suite + lint**

Run: `uv run --extra dev pytest -q` (all green) and `UV_LOCK_TIMEOUT=25 uv run --with ruff ruff check src tests` (All checks passed!).

- [ ] **Step 4: Commit and push**

```bash
git add README.md CHANGELOG.md
git commit -m "docs: mark Phase 5 (consolidation) complete"
git push
```

---

## Self-Review

**Spec coverage** (design spec §13 "Consolidation — memify-style self-improvement"):
- `memify`-style self-improvement: mine journal → curated per-kind insight notes (deduped, idempotent, indexed) → Tasks 1, 3
- Duplicate detection (a memify signal) → Task 1 (`find_duplicate_entries`)
- Access-frequency surfacing (reweight by usage) → Task 2 (`db.top_accessed`; access_count tracked since Phase 2)
- `torsor consolidate` + `consolidate` MCP tool → Task 4
- Completes a Coach fast-follow: insight auto-mining now exists and feeds the Coach's `learning` recs (insights live in EPISODIC tier).
- **Deferred (documented):** HTTP/team transport (`torsor mcp --http`) — FastMCP transport API is version-fragile and not safely unit-testable headless (same call as the deferred sampling guard); auto-pruning of stale notes — consolidation never deletes source Markdown (Markdown is truth); it reports and adds derived insights only.

**Placeholder scan:** none — every code/test step is runnable.

**Type consistency:** `coach.mining.{parse_journal_entries,mine_insights,find_duplicate_entries}`, `db.top_accessed`, `operations.consolidate` match the locked contracts. `mine_insights` writes `Frontmatter(type="insight", kind=...)` (extra-allowed, indexer reads `kind`). `consolidate` reuses `_open_index`/`_embedder_for`/`reindex` from Phase 2. Tests use the journal format produced by `store.append_journal`.

## Notes for the implementer
- `coach/mining.py` is pure (store + models + stdlib `re`); it must NOT import `operations` (no cycle — `operations` imports `coach`, not the reverse).
- `mine_insights` overwrites `insights/<kind>.md` each run (idempotent); it dedupes bullets and is safe to run repeatedly. It only *adds* derived notes — no source Markdown is ever deleted.
- `consolidate` reindexes after mining so the new insight notes are immediately recallable (the `test_consolidate_insight_is_recallable` test proves the loop).
