# torsor-helper Phase 6 (Coach) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Coach — an independent, non-intrusive advisor that emits recommendations to keep the knowledge base healthy (hygiene/maturity) and steer toward best practices (anti-duplication + relevant decisions/learnings) — surfaced via a `recommend()` MCP tool and a `torsor coach` CLI report, with dismissal/decay so it never nags.

**Architecture:** A pure `coach/` package: `health.py` runs deterministic hygiene checks over project state (`thin`/`stale`/`unruled`/`uncharted`); `recommender.py` produces retrieval-based best-practice recs (`reuse` from the symbol map, `decision`/`learning` from memory) given a DB connection + embedder; `report.py` assembles both families, applies dismissal/decay (`state.py`), ranks by severity, and budgets. `operations.recommend` is the orchestrator (it opens/syncs the index and hands `coach` a connection + embedder, avoiding an import cycle); `server`/`cli` are thin adapters. Every recommendation carries a stable `key`, an `action`, and a `source` citation.

**Tech Stack:** Python ≥3.11 stdlib (`json`); builds on shipped `models`/`store`/`templates`/`guard`/`cartographer`/`db`/`search`/`embeddings`/`config`/`operations`.

**Deferred (documented fast-follows):** insight auto-mining (`mine_insights`); weaving recs into `bootstrap_session`/`get_intent`/`check_drift` outputs; severity *escalation* over repeated checkups (decay/dismiss ship now). These extend the Coach without changing its surface.

---

## File Structure

```
src/torsor_helper/models.py        # MODIFY: add Recommendation
src/torsor_helper/coach/__init__.py
src/torsor_helper/coach/health.py      # deterministic hygiene checks (pure: store + templates + guard + cartographer)
src/torsor_helper/coach/state.py       # CoachState: coach_state.json (dismiss / seen / decay)
src/torsor_helper/coach/recommender.py # best-practice recs (reuse via symbols; decision/learning via search) — takes conn+embedder
src/torsor_helper/coach/report.py      # assemble(): health + recommender + state filter + severity rank + budget
src/torsor_helper/operations.py    # MODIFY: add recommend() + dismiss_recommendation()
src/torsor_helper/server.py        # MODIFY: replace recommend stub with real ops.recommend
src/torsor_helper/cli.py           # MODIFY: add `torsor coach`
tests/test_coach_models.py
tests/test_coach_health.py
tests/test_coach_state.py
tests/test_coach_recommender.py
tests/test_coach_report.py
tests/test_recommend_op.py
tests/test_cli_coach.py
```

## Interface contracts (locked — use these exact names)

- `models.Recommendation(BaseModel)`: `kind:str`, `severity:str="suggest"` (info|suggest|important), `message:str`, `action:str=""`, `source:str=""`, `key:str`, `score:float=0.0`.
- `coach.health`: `check_thin(store)`, `check_stale(store)`, `check_unruled(store)`, `check_uncharted(store, modules_in_map:set[str])`, `run_health(store, modules_in_map:set[str])` — each `-> list[Recommendation]`.
- `coach.state.CoachState(path)`: `.is_dismissed(key)->bool`, `.dismiss(key)`, `.seen(key)`, `.times_shown(key)->int`, `.save()`.
- `coach.recommender.best_practice_recs(store, config, context, conn, embedder, limit=5) -> list[Recommendation]`.
- `coach.report.assemble(store, config, context=None, limit=8, conn=None, embedder=None) -> list[Recommendation]`.
- `operations.recommend(store, config, context=None, limit=8) -> list[Recommendation]`; `operations.dismiss_recommendation(store, key) -> None`.

---

### Task 1: Recommendation model

**Files:**
- Modify: `src/torsor_helper/models.py`
- Create: `tests/test_coach_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_coach_models.py
from torsor_helper.models import Recommendation


def test_recommendation_defaults():
    r = Recommendation(kind="thin", message="fill the charter", key="thin:charter")
    assert r.severity == "suggest"
    assert r.action == "" and r.source == "" and r.score == 0.0


def test_recommendation_full():
    r = Recommendation(kind="reuse", severity="important", message="reuse format_date",
                       action="Reuse format_date", source="utils/dates.py:12", key="reuse:x", score=3.0)
    assert r.kind == "reuse" and r.severity == "important" and r.score == 3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_coach_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'Recommendation'`

- [ ] **Step 3: Implement** — add to `src/torsor_helper/models.py` (after `Violation`):

```python
class Recommendation(BaseModel):
    kind: str          # thin | stale | unruled | uncharted | reuse | decision | learning
    severity: str = "suggest"  # info | suggest | important
    message: str
    action: str = ""
    source: str = ""
    key: str           # stable id for dedup / dismissal / decay
    score: float = 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_coach_models.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/models.py tests/test_coach_models.py
git commit -m "feat: Recommendation model"
```

---

### Task 2: Hygiene checks (`coach/health.py`)

**Files:**
- Create: `src/torsor_helper/coach/__init__.py` (empty)
- Create: `src/torsor_helper/coach/health.py`
- Create: `tests/test_coach_health.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_coach_health.py
from datetime import datetime

from torsor_helper.coach import health
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_thin_flags_untouched_seed_files(tmp_path):
    store = _store(tmp_path)  # fresh scaffold == seed templates
    kinds = {r.kind for r in health.check_thin(store)}
    keys = {r.key for r in health.check_thin(store)}
    assert kinds == {"thin"}
    assert {"thin:charter", "thin:system_patterns", "thin:tech_context"} <= keys


def test_thin_clears_when_filled(tmp_path):
    store = _store(tmp_path)
    store.paths.charter.write_text("---\ntype: charter\n---\n\n# Charter\n\nReal content here.\n")
    keys = {r.key for r in health.check_thin(store)}
    assert "thin:charter" not in keys


def test_stale_flags_untouched_active_context(tmp_path):
    store = _store(tmp_path)
    recs = health.check_stale(store)
    assert any(r.kind == "stale" and r.key == "stale:active" for r in recs)


def test_unruled_flags_decisions_without_rules(tmp_path):
    store = _store(tmp_path)
    # add a second decision (seed already wrote 0001), neither carries rules
    (store.paths.decisions_dir / "0002-x.md").write_text("---\ntype: decision\n---\n\n# ADR 0002: x\n\nb\n")
    recs = health.check_unruled(store)
    assert any(r.kind == "unruled" for r in recs)


def test_unruled_clears_when_a_rule_exists(tmp_path):
    store = _store(tmp_path)
    (store.paths.decisions_dir / "0002-x.md").write_text(
        "---\ntype: decision\nrules:\n  - kind: forbid_import\n    target: requests\n---\n\n# ADR 0002: x\n\nb\n"
    )
    assert health.check_unruled(store) == []


def test_uncharted_flags_unmapped_source(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "app.py").write_text("def run():\n    return 1\n")
    recs = health.check_uncharted(store, modules_in_map=set())  # nothing mapped
    assert any(r.kind == "uncharted" for r in recs)
    # once mapped, it clears
    assert health.check_uncharted(store, modules_in_map={"app.py"}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_coach_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.coach'`

- [ ] **Step 3: Implement**

Create `src/torsor_helper/coach/__init__.py` (empty file).

Create `src/torsor_helper/coach/health.py`:
```python
from __future__ import annotations

from torsor_helper import cartographer, templates
from torsor_helper.guard import load_rules
from torsor_helper.models import Recommendation
from torsor_helper.store import Store

_THIN_TARGETS = [
    ("charter", "Charter", templates.CHARTER),
    ("system_patterns", "System patterns", templates.SYSTEM_PATTERNS),
    ("tech_context", "Tech context", templates.TECH_CONTEXT),
]


def check_thin(store: Store) -> list[Recommendation]:
    out: list[Recommendation] = []
    for attr, label, seed in _THIN_TARGETS:
        path = getattr(store.paths, attr)
        if path.exists() and path.read_text(encoding="utf-8").strip() == seed.strip():
            out.append(Recommendation(
                kind="thin", severity="important",
                message=f"{label} is still the seed template — fill it in so the agent has real context.",
                action=f"Edit {path}", source=str(path), key=f"thin:{attr}",
            ))
    return out


def check_stale(store: Store) -> list[Recommendation]:
    path = store.paths.active_context
    if path.exists() and path.read_text(encoding="utf-8").strip() == templates.ACTIVE_CONTEXT.strip():
        return [Recommendation(
            kind="stale", severity="suggest",
            message="Active context is still the seed template — capture current focus with update_active / handoff.",
            action="run handoff or update_active", source=str(path), key="stale:active",
        )]
    return []


def check_unruled(store: Store) -> list[Recommendation]:
    decisions = sorted(store.paths.decisions_dir.glob("*.md")) if store.paths.decisions_dir.exists() else []
    rules = load_rules(store)
    if len(decisions) >= 2 and not rules:
        return [Recommendation(
            kind="unruled", severity="suggest",
            message=f"{len(decisions)} decisions recorded but no machine-readable rules — formalize the load-bearing ones so the guard can enforce them.",
            action="add a rules: block to an ADR's frontmatter", source=str(store.paths.decisions_dir), key="unruled",
        )]
    return []


def check_uncharted(store: Store, modules_in_map: set[str]) -> list[Recommendation]:
    source = {p.relative_to(store.paths.root).as_posix() for p in cartographer.iter_source_files(store.paths.root)}
    missing = sorted(source - modules_in_map)
    if not missing:
        return []
    return [Recommendation(
        kind="uncharted", severity="suggest",
        message=f"{len(missing)} source module(s) not in the map (e.g. {missing[0]}) — run `torsor map`.",
        action="torsor map", source=missing[0], key="uncharted",
    )]


def run_health(store: Store, modules_in_map: set[str]) -> list[Recommendation]:
    return [
        *check_thin(store),
        *check_stale(store),
        *check_unruled(store),
        *check_uncharted(store, modules_in_map),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_coach_health.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/coach/__init__.py src/torsor_helper/coach/health.py tests/test_coach_health.py
git commit -m "feat: coach hygiene checks (thin/stale/unruled/uncharted)"
```

---

### Task 3: Dismissal/decay state (`coach/state.py`)

**Files:**
- Create: `src/torsor_helper/coach/state.py`
- Create: `tests/test_coach_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_coach_state.py
from torsor_helper.coach.state import CoachState


def test_dismiss_and_persist(tmp_path):
    p = tmp_path / "coach_state.json"
    state = CoachState(p)
    assert state.is_dismissed("thin:charter") is False
    state.dismiss("thin:charter")
    state.save()
    # reload from disk
    reloaded = CoachState(p)
    assert reloaded.is_dismissed("thin:charter") is True


def test_seen_counts(tmp_path):
    state = CoachState(tmp_path / "coach_state.json")
    state.seen("uncharted")
    state.seen("uncharted")
    assert state.times_shown("uncharted") == 2
    assert state.times_shown("never") == 0


def test_corrupt_state_resets(tmp_path):
    p = tmp_path / "coach_state.json"
    p.write_text("{not valid json")
    state = CoachState(p)  # must not raise
    assert state.is_dismissed("x") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_coach_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.coach.state'`

- [ ] **Step 3: Implement** — `src/torsor_helper/coach/state.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


class CoachState:
    """Per-recommendation tracking (dismissed / times_shown), persisted as JSON.

    Derived and disposable — a corrupt or missing file resets cleanly.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.data, dict):
                self.data = {}
        except (OSError, ValueError):
            self.data = {}

    def _entry(self, key: str) -> dict:
        return self.data.setdefault(key, {})

    def is_dismissed(self, key: str) -> bool:
        return bool(self.data.get(key, {}).get("dismissed", False))

    def dismiss(self, key: str) -> None:
        self._entry(key)["dismissed"] = True

    def seen(self, key: str) -> None:
        entry = self._entry(key)
        entry["times_shown"] = int(entry.get("times_shown", 0)) + 1

    def times_shown(self, key: str) -> int:
        return int(self.data.get(key, {}).get("times_shown", 0))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_coach_state.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/coach/state.py tests/test_coach_state.py
git commit -m "feat: CoachState (dismissal/decay, JSON-backed, disposable)"
```

---

### Task 4: Best-practice recommender (`coach/recommender.py`)

**Files:**
- Create: `src/torsor_helper/coach/recommender.py`
- Create: `tests/test_coach_recommender.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_coach_recommender.py
from datetime import datetime

from torsor_helper import db
from torsor_helper.coach.recommender import best_practice_recs
from torsor_helper.config import TorsorConfig
from torsor_helper.embeddings import HashingEmbedder
from torsor_helper.indexer import reindex
from torsor_helper.models import Symbol
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _indexed(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    store.append_journal("Learned: cache the embedder per process", kind="learning", links=[])
    conn = db.connect(tmp_path / "idx.db")
    reindex(store, conn, HashingEmbedder(dim=128))
    db.replace_all_symbols(conn, [
        Symbol(name="format_date", kind="function", signature="format_date(d)", module="utils/dates.py", line=12, doc="Format.", refs=3),
    ])
    return store, conn


def test_reuse_rec_from_symbol_inventory(tmp_path):
    store, conn = _indexed(tmp_path)
    recs = best_practice_recs(store, TorsorConfig(), "format date", conn=conn, embedder=HashingEmbedder(dim=128))
    reuse = [r for r in recs if r.kind == "reuse"]
    assert reuse
    assert "format_date(d)" in reuse[0].message
    assert reuse[0].source == "utils/dates.py:12"


def test_no_conn_returns_empty(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    assert best_practice_recs(store, TorsorConfig(), "anything", conn=None, embedder=None) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_coach_recommender.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.coach.recommender'`

- [ ] **Step 3: Implement** — `src/torsor_helper/coach/recommender.py`:

```python
from __future__ import annotations

from torsor_helper import db
from torsor_helper.models import Recommendation, Tier
from torsor_helper.search import hybrid_search
from torsor_helper.store import Store

# Map the tier of a recalled note to a best-practice recommendation kind.
_TIER_KIND = {Tier.ARCHITECTURE: "decision", Tier.EPISODIC: "learning"}


def best_practice_recs(store: Store, config, context, conn, embedder, limit: int = 5) -> list[Recommendation]:
    if conn is None or embedder is None or not context:
        return []
    out: list[Recommendation] = []

    # 1. Reuse: existing symbols that match the context (anti-duplication).
    for sym in db.search_symbols(conn, context, limit=3):
        out.append(Recommendation(
            kind="reuse", severity="suggest",
            message=f"`{sym.signature}` already exists in {sym.module}:{sym.line} — reuse it instead of reimplementing.",
            action=f"reuse {sym.name}", source=f"{sym.module}:{sym.line}",
            key=f"reuse:{sym.module}:{sym.name}", score=float(sym.refs),
        ))

    # 2. Relevant prior decisions / learnings from memory.
    result = hybrid_search(conn, embedder, config, context, limit=limit)
    for hit in result.hits:
        kind = _TIER_KIND.get(hit.tier)
        if kind is None:
            continue
        verb = "decided" if kind == "decision" else "learned"
        out.append(Recommendation(
            kind=kind, severity="info",
            message=f"You previously {verb} something relevant: {hit.title} — {hit.snippet[:120]}",
            action=f"review {hit.path}", source=hit.path,
            key=f"{kind}:{hit.path}", score=hit.score,
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_coach_recommender.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/coach/recommender.py tests/test_coach_recommender.py
git commit -m "feat: coach best-practice recs (reuse + relevant decisions/learnings)"
```

---

### Task 5: Report assembly (`coach/report.py`)

**Files:**
- Create: `src/torsor_helper/coach/report.py`
- Create: `tests/test_coach_report.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_coach_report.py
from datetime import datetime

from torsor_helper.coach import report
from torsor_helper.coach.state import CoachState
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_assemble_returns_hygiene_recs_without_index(tmp_path):
    store = _store(tmp_path)  # fresh scaffold -> thin + stale present; no conn
    recs = report.assemble(store, TorsorConfig(), conn=None, embedder=None)
    kinds = {r.kind for r in recs}
    assert "thin" in kinds  # important hygiene rec surfaces
    # important severity ranks first
    assert recs[0].severity == "important"


def test_assemble_respects_dismissals(tmp_path):
    store = _store(tmp_path)
    state = CoachState(store.paths.index_dir / "coach_state.json")
    state.dismiss("thin:charter")
    state.save()
    recs = report.assemble(store, TorsorConfig(), conn=None, embedder=None)
    assert all(r.key != "thin:charter" for r in recs)


def test_assemble_limits_and_records_seen(tmp_path):
    store = _store(tmp_path)
    recs = report.assemble(store, TorsorConfig(), conn=None, embedder=None, limit=1)
    assert len(recs) == 1
    state = CoachState(store.paths.index_dir / "coach_state.json")
    assert state.times_shown(recs[0].key) >= 1  # shown was persisted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_coach_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.coach.report'`

- [ ] **Step 3: Implement** — `src/torsor_helper/coach/report.py`:

```python
from __future__ import annotations

from torsor_helper import db
from torsor_helper.coach import health, recommender
from torsor_helper.coach.state import CoachState
from torsor_helper.models import Recommendation
from torsor_helper.store import Store

_SEVERITY_RANK = {"important": 0, "suggest": 1, "info": 2}


def assemble(store: Store, config, context=None, limit: int = 8, conn=None, embedder=None) -> list[Recommendation]:
    modules_in_map: set[str] = set(db.modules(conn)) if conn is not None else set()

    recs: list[Recommendation] = health.run_health(store, modules_in_map)
    if context:
        recs += recommender.best_practice_recs(store, config, context, conn=conn, embedder=embedder, limit=limit)

    state = CoachState(store.paths.index_dir / "coach_state.json")
    recs = [r for r in recs if not state.is_dismissed(r.key)]
    recs.sort(key=lambda r: (_SEVERITY_RANK.get(r.severity, 1), -r.score, r.key))
    recs = recs[:limit]

    for rec in recs:
        state.seen(rec.key)
    state.save()
    return recs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_coach_report.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/coach/report.py tests/test_coach_report.py
git commit -m "feat: coach report assembly (health + recs + dismissal + ranking)"
```

---

### Task 6: `operations.recommend` + `dismiss_recommendation`

**Files:**
- Modify: `src/torsor_helper/operations.py`
- Create: `tests/test_recommend_op.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recommend_op.py
from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.coach.state import CoachState
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_recommend_surfaces_hygiene_on_fresh_project(tmp_path):
    store = _store(tmp_path)
    recs = ops.recommend(store, TorsorConfig())
    assert any(r.kind == "thin" for r in recs)


def test_recommend_with_context_includes_reuse(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "app.py").write_text("def format_date(d):\n    return d\n")
    ops.map_repo(store, TorsorConfig())  # builds index + symbols
    recs = ops.recommend(store, TorsorConfig(), context="format date")
    assert any(r.kind == "reuse" and "format_date" in r.message for r in recs)


def test_dismiss_recommendation_persists(tmp_path):
    store = _store(tmp_path)
    ops.dismiss_recommendation(store, "thin:charter")
    recs = ops.recommend(store, TorsorConfig())
    assert all(r.key != "thin:charter" for r in recs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_recommend_op.py -v`
Expected: FAIL — `AttributeError: module 'torsor_helper.operations' has no attribute 'recommend'`

- [ ] **Step 3: Implement** — append to `operations.py` (add `from torsor_helper.coach import report as coach_report` and `from torsor_helper.coach.state import CoachState` to imports):

```python
def recommend(store, config, context=None, limit=8):
    conn = _open_index(store, config)
    embedder = _embedder_for(config) if conn is not None else None
    try:
        return coach_report.assemble(store, config, context=context, limit=limit, conn=conn, embedder=embedder)
    finally:
        if conn is not None:
            conn.close()


def dismiss_recommendation(store, key) -> None:
    state = CoachState(store.paths.index_dir / "coach_state.json")
    state.dismiss(key)
    state.save()
```

> Note on import order: `coach.report` imports `coach.health`/`coach.recommender`, which import `guard`/`cartographer`/`db`/`search` — none of which import `operations`, so adding the `coach` imports to `operations` introduces no cycle. (`operations` is the only module that imports `coach`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_recommend_op.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full suite**

Run: `uv run --extra dev pytest -q`
Expected: PASS (all green).

- [ ] **Step 6: Commit**

```bash
git add src/torsor_helper/operations.py tests/test_recommend_op.py
git commit -m "feat: operations.recommend + dismiss_recommendation"
```

---

### Task 7: MCP `recommend` tool (replace stub) + `torsor coach` CLI

**Files:**
- Modify: `src/torsor_helper/server.py`
- Modify: `src/torsor_helper/cli.py`
- Create: `tests/test_cli_coach.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_coach.py
from typer.testing import CliRunner

from torsor_helper.cli import app

runner = CliRunner()


def test_coach_reports_hygiene_on_fresh_project(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["coach", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "seed template" in result.output.lower()  # the `thin` hygiene rec


def test_coach_dismiss_then_hidden(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    runner.invoke(app, ["coach", "--root", str(tmp_path), "--dismiss", "thin:charter"])
    result = runner.invoke(app, ["coach", "--root", str(tmp_path)])
    assert "thin:charter" not in result.output  # dismissed key no longer surfaces


def test_coach_requires_init(tmp_path):
    result = runner.invoke(app, ["coach", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "not initialized" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_cli_coach.py -v`
Expected: FAIL — no `coach` command.

- [ ] **Step 3: Implement**

In `server.py`, replace the existing `recommend` stub with the real delegation:
```python
    @mcp.tool()
    def recommend(context: str = "", limit: int = 8) -> str:
        """Health + best-practice recommendations (the Coach). Pass a context (e.g. what you're about to build) for reuse hints."""
        recs = ops.recommend(store, config, context or None, limit=limit)
        if not recs:
            return "No recommendations right now — the project looks healthy."
        lines = []
        for r in recs:
            tail = f" → {r.action}" if r.action else ""
            lines.append(f"- [{r.severity}/{r.kind}] {r.message}{tail}  (key: {r.key})")
        return "\n".join(lines)
```

In `cli.py`, add (uses `ops`, `load_config`, `Store`, `TorsorPaths` already imported):
```python
@app.command()
def coach(
    context: list[str] = typer.Argument(None, help="Optional context for best-practice hints (e.g. what you're building)."),
    root: Path = typer.Option(Path("."), help="Project root."),
    dismiss: str = typer.Option(None, help="Dismiss a recommendation by its key."),
) -> None:
    """Show health + best-practice recommendations (the Coach). Advisory; never blocks."""
    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(tp)
    store = Store(tp)
    if dismiss:
        ops.dismiss_recommendation(store, dismiss)
        typer.echo(f"Dismissed {dismiss}.")
        return
    recs = ops.recommend(store, config, " ".join(context) if context else None)
    if not recs:
        typer.echo("No recommendations right now — the project looks healthy.")
        return
    for r in recs:
        tail = f" -> {r.action}" if r.action else ""
        typer.echo(f"[{r.severity}/{r.kind}] {r.message}{tail}  (key: {r.key})")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_cli_coach.py -v`
Expected: PASS (3 passed). Then `uv run --extra dev pytest -q` → full suite green. The existing `test_coach_hooks.py::test_server_registers_recommend_stub` only checks that `recommend` is registered (still true), so it stays green.

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/server.py src/torsor_helper/cli.py tests/test_cli_coach.py
git commit -m "feat: real recommend MCP tool + torsor coach CLI"
```

---

### Task 8: Dogfood smoke + README/CHANGELOG sync + self-review

**Files:**
- Modify: `README.md`, `CHANGELOG.md`

- [ ] **Step 1: Dogfood — run the Coach on the project itself**

```bash
cd /Users/magnetoid/Documents/trae_projects/torsor-mem
uv run torsor coach 2>&1 | head -15
uv run torsor coach "hybrid search index" 2>&1 | head -15
```
Expected: hygiene recs reflect the real project state (the dogfooded `.torsor/` is already filled, so `thin` should NOT fire for charter/system-patterns/tech-context; `uncharted` may fire if the map is stale). With a context, `reuse` recs cite real symbols (e.g. `hybrid_search`). No traceback; exit 0.

- [ ] **Step 2: Update README + CHANGELOG**

In `README.md`: change the Phase 6 roadmap line to `- [x]`; move the `recommend(context?)` tool row to `✅ **shipped**` (drop the "stub today" note); bump the status badge to `Phase 6 shipped` and the test count. Add a Coach `### 🩺` note that `torsor coach` is live.

In `CHANGELOG.md`: add a "Phase 6 — Coach" section under Unreleased (hygiene checks, best-practice reuse + relevant-memory recs, `recommend` tool, `torsor coach` CLI, dismissal/decay; insight-mining + woven-in surfaces deferred).

- [ ] **Step 3: Run the full suite + lint**

Run: `uv run --extra dev pytest -q` (all green) and `UV_LOCK_TIMEOUT=25 uv run --with ruff ruff check src tests` (All checks passed!).

- [ ] **Step 4: Commit and push**

```bash
git add README.md CHANGELOG.md
git commit -m "docs: mark Phase 6 (Coach) complete"
git push
```

---

## Self-Review

**Spec coverage** (Coach design spec §3–§9):
- Recommendation model (kind/severity/message/action/source/key/score) → Task 1
- Family A — hygiene/maturity (`thin`/`stale`/`unruled`/`uncharted`) → Task 2
- Family B — best-practice (`reuse` + `decision`/`learning`) → Task 4
- Delivery: `recommend()` tool + `torsor coach` report → Task 7 (woven-into-other-tools auto-injection deferred & documented)
- Noise control: dismissal + seen/decay (`coach_state.json`, derived/disposable) → Tasks 3, 5
- Ranking by severity + score + token-style limit → Task 5
- Orchestration without import cycle (operations hands coach a conn+embedder) → Task 6
- **Deferred (documented):** insight auto-mining (`mine_insights`); severity *escalation* over repeat checkups; weaving recs into bootstrap/get_intent/check_drift outputs. These extend, not block.

**Placeholder scan:** none — every code/test step is runnable.

**Type consistency:** `Recommendation` fields match across `models`/`health`/`recommender`/`report`; `coach.health.*`, `coach.state.CoachState`, `coach.recommender.best_practice_recs`, `coach.report.assemble`, `operations.recommend/dismiss_recommendation` align with the locked contracts. `report.assemble` and `operations.recommend` share the `conn`/`embedder` threading. `_TIER_KIND` maps `Tier.ARCHITECTURE`→decision, `Tier.EPISODIC`→learning (consistent with how `map_repo`/`store` tier notes).

## Notes for the implementer
- The `coach/` package must not import `operations` (avoids a cycle) — it receives a DB `conn` + `embedder` from `operations.recommend`. Keep `health.py` pure (no index needed); `recommender.py` needs the conn+embedder and returns `[]` when they're absent.
- `coach_state.json` lives in `.torsor/.index/` (already git-ignored, derived/disposable) — consistent with "Markdown is truth, index is throwaway".
- `check_thin`/`check_stale` compare against the *seed templates* (`templates.CHARTER` etc.), so they clear the moment a human/agent edits the file. This is why the dogfooded project (already filled) won't nag.
