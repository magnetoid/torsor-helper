# torsor-helper Phase 1 (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an installable Python MCP server + CLI that scaffolds the pyramidal-wiki (`.torsor/`) and exposes the core collapse-fighting tools (`bootstrap_session`, `recall`, `remember`, `update_active`, `handoff`), with Markdown as the source of truth.

**Architecture:** Markdown files under `.torsor/` are the durable substrate. A thin, fully-tested `operations` layer implements all behavior over a `Store` (filesystem) + `TorsorConfig`. `server.py` is a FastMCP adapter that wires those operations to MCP tools/resources; `cli.py` is a Typer adapter (`init`/`mcp`/`doctor`). No database, embeddings, tree-sitter, or drift detection in Phase 1 — `recall` is deterministic keyword search over the Markdown (SQLite/vectors arrive in Phase 2).

**Tech Stack:** Python ≥3.11, `mcp` (FastMCP), `pydantic` v2, `pyyaml`, `tomli-w` (+ stdlib `tomllib`), `typer`; dev: `pytest`, `anyio`.

---

## File Structure

```
pyproject.toml                     # package metadata, deps, `torsor` script
src/torsor_helper/__init__.py         # __version__
src/torsor_helper/models.py           # Tier, MemoryKind, Frontmatter, Note, RecallHit, RecallResult
src/torsor_helper/paths.py            # TorsorPaths — resolves the .torsor/ layout from a root
src/torsor_helper/templates.py        # seed Markdown for scaffolding
src/torsor_helper/budget.py           # estimate_tokens / truncate_to_tokens
src/torsor_helper/config.py           # TorsorConfig + load_config/save_config (torsor.toml)
src/torsor_helper/store.py            # Store — file I/O, frontmatter/wikilink parsing, scaffold, journal
src/torsor_helper/recall.py           # keyword_recall (Phase-1 retrieval)
src/torsor_helper/operations.py       # bootstrap_session/recall/remember/update_active/record_handoff
src/torsor_helper/clients.py          # MCP client config snippets
src/torsor_helper/server.py           # build_server (FastMCP) + run
src/torsor_helper/cli.py              # Typer app: init / mcp / doctor
tests/conftest.py                  # tmp_project fixture, FIXED_CLOCK
tests/test_*.py                    # one per module
```

## Interface contracts (locked — use these exact names everywhere)

- `Tier(IntEnum)`: `CHARTER=0, ARCHITECTURE=1, MAP=2, ACTIVE=3, EPISODIC=4`
- `MemoryKind(str, Enum)`: `OBSERVATION="observation", DECISION="decision", LEARNING="learning", BLOCKER="blocker", HANDOFF="handoff"`
- `Frontmatter(BaseModel)`: `type:str`, `status:str="active"`, `tags:list[str]=[]`, `links:list[str]=[]`, `created:str|None=None`, `updated:str|None=None` (extra allowed)
- `Note(BaseModel)`: `path:Path`, `tier:Tier`, `frontmatter:Frontmatter`, `title:str`, `body:str`, `content_hash:str`
- `RecallHit(BaseModel)`: `path:str`, `title:str`, `tier:Tier`, `score:float`, `snippet:str`
- `RecallResult(BaseModel)`: `query:str`, `hits:list[RecallHit]`, `total_tokens:int`
- `TorsorPaths(root: Path)` with attributes: `base, config_file, charter, architecture_dir, system_patterns, tech_context, decisions_dir, map_dir, map_overview, active_dir, active_context, progress, memory_dir, journal_dir, index_dir, index_db` and method `journal_file(date_str: str) -> Path`
- `estimate_tokens(text, chars_per_token=4) -> int`; `truncate_to_tokens(text, max_tokens, chars_per_token=4) -> str`
- `TorsorConfig` with `.budgets` (`bootstrap_tokens=2000, recall_tokens=1500, chars_per_token=4`) and `.embeddings`; `load_config(paths)`, `save_config(paths, config)`
- `Store(paths: TorsorPaths, clock: Callable[[], datetime] = datetime.now)` with methods `scaffold(force=False)`, `write_note(path, frontmatter, title, body) -> Note`, `read_note(path) -> Note`, `iter_notes() -> Iterator[Note]`, `append_journal(content, kind, links) -> Path`; static `parse_frontmatter(text)`, `serialize(frontmatter, title, body)`, `extract_wikilinks(text)`, `content_hash(text)`, `tier_for_path(paths, path)`
- `keyword_recall(notes, query, limit=8, chars_per_token=4, max_tokens=1500, tier_weights=None) -> RecallResult`
- `operations.bootstrap_session(store, config) -> str`, `operations.recall(store, config, query, limit=8) -> RecallResult`, `operations.remember(store, content, kind="observation", links=None) -> str`, `operations.update_active(store, focus, progress, open_questions) -> None`, `operations.record_handoff(store, summary, decisions="", open_questions="", next_steps="") -> str`
- `clients.SUPPORTED_CLIENTS: dict[str,str]`; `clients.config_snippet(client, root) -> str`
- `server.build_server(root: Path) -> FastMCP`; `server.run(root: Path) -> None`

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/torsor_helper/__init__.py`
- Create: `tests/test_package.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_package.py
import torsor_helper


def test_version_exposed():
    assert isinstance(torsor_helper.__version__, str)
    assert torsor_helper.__version__.count(".") >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_package.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper'`

- [ ] **Step 3: Write pyproject.toml and the package init**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "torsor-helper"
version = "0.1.0"
description = "Persistent memory + architectural-intent guardrail for AI coding agents, over MCP."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.2.0",
    "pydantic>=2.6",
    "pyyaml>=6.0",
    "tomli-w>=1.0",
    "typer>=0.12",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "anyio>=4.0"]

[project.scripts]
torsor = "torsor_helper.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/torsor_helper"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
```

```python
# src/torsor_helper/__init__.py
"""torsor-helper: persistent memory + architectural-intent guardrail over MCP."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Install editable and run the test**

Run: `pip install -e ".[dev]" && pytest tests/test_package.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/torsor_helper/__init__.py tests/test_package.py
git commit -m "feat: package scaffolding for torsor-helper"
```

---

### Task 2: Domain models

**Files:**
- Create: `src/torsor_helper/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from pathlib import Path

from torsor_helper.models import (
    Frontmatter, MemoryKind, Note, RecallHit, RecallResult, Tier,
)


def test_tier_ordering():
    assert Tier.CHARTER < Tier.ARCHITECTURE < Tier.MAP < Tier.ACTIVE < Tier.EPISODIC


def test_memory_kind_values():
    assert MemoryKind.OBSERVATION.value == "observation"
    assert MemoryKind.HANDOFF.value == "handoff"


def test_frontmatter_defaults_and_extra():
    fm = Frontmatter(type="charter", custom_field="ok")
    assert fm.status == "active"
    assert fm.tags == [] and fm.links == []
    assert fm.model_dump()["custom_field"] == "ok"


def test_note_round_trips_fields():
    note = Note(
        path=Path(".torsor/charter.md"),
        tier=Tier.CHARTER,
        frontmatter=Frontmatter(type="charter"),
        title="Charter",
        body="Body text",
        content_hash="abc",
    )
    assert note.tier is Tier.CHARTER
    assert note.title == "Charter"


def test_recall_result_holds_hits():
    hit = RecallHit(path="a.md", title="A", tier=Tier.EPISODIC, score=1.0, snippet="x")
    res = RecallResult(query="q", hits=[hit], total_tokens=5)
    assert res.hits[0].title == "A"
    assert res.total_tokens == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.models'`

- [ ] **Step 3: Write the implementation**

```python
# src/torsor_helper/models.py
from __future__ import annotations

from enum import Enum, IntEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Tier(IntEnum):
    CHARTER = 0
    ARCHITECTURE = 1
    MAP = 2
    ACTIVE = 3
    EPISODIC = 4


class MemoryKind(str, Enum):
    OBSERVATION = "observation"
    DECISION = "decision"
    LEARNING = "learning"
    BLOCKER = "blocker"
    HANDOFF = "handoff"


class Frontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    status: str = "active"
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    created: str | None = None
    updated: str | None = None


class Note(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    tier: Tier
    frontmatter: Frontmatter
    title: str
    body: str
    content_hash: str


class RecallHit(BaseModel):
    path: str
    title: str
    tier: Tier
    score: float
    snippet: str


class RecallResult(BaseModel):
    query: str
    hits: list[RecallHit] = Field(default_factory=list)
    total_tokens: int = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/models.py tests/test_models.py
git commit -m "feat: domain models (Tier, Frontmatter, Note, RecallResult)"
```

---

### Task 3: Path layout

**Files:**
- Create: `src/torsor_helper/paths.py`
- Create: `tests/test_paths.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_paths.py
from pathlib import Path

from torsor_helper.paths import TorsorPaths


def test_layout_under_dot_torsor(tmp_path: Path):
    p = TorsorPaths(tmp_path)
    assert p.base == tmp_path / ".torsor"
    assert p.charter == tmp_path / ".torsor" / "charter.md"
    assert p.system_patterns == tmp_path / ".torsor" / "architecture" / "system-patterns.md"
    assert p.decisions_dir == tmp_path / ".torsor" / "architecture" / "decisions"
    assert p.active_context == tmp_path / ".torsor" / "active" / "context.md"
    assert p.journal_dir == tmp_path / ".torsor" / "memory" / "journal"
    assert p.index_db == tmp_path / ".torsor" / ".index" / "torsor.db"


def test_journal_file_by_date(tmp_path: Path):
    p = TorsorPaths(tmp_path)
    assert p.journal_file("2026-06-01") == p.journal_dir / "2026-06-01.md"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.paths'`

- [ ] **Step 3: Write the implementation**

```python
# src/torsor_helper/paths.py
from __future__ import annotations

from pathlib import Path


class TorsorPaths:
    """Resolves the .torsor/ directory layout relative to a project root."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    @property
    def base(self) -> Path:
        return self.root / ".torsor"

    @property
    def config_file(self) -> Path:
        return self.base / "torsor.toml"

    @property
    def charter(self) -> Path:
        return self.base / "charter.md"

    @property
    def architecture_dir(self) -> Path:
        return self.base / "architecture"

    @property
    def system_patterns(self) -> Path:
        return self.architecture_dir / "system-patterns.md"

    @property
    def tech_context(self) -> Path:
        return self.architecture_dir / "tech-context.md"

    @property
    def decisions_dir(self) -> Path:
        return self.architecture_dir / "decisions"

    @property
    def map_dir(self) -> Path:
        return self.base / "map"

    @property
    def map_overview(self) -> Path:
        return self.map_dir / "overview.md"

    @property
    def active_dir(self) -> Path:
        return self.base / "active"

    @property
    def active_context(self) -> Path:
        return self.active_dir / "context.md"

    @property
    def progress(self) -> Path:
        return self.active_dir / "progress.md"

    @property
    def memory_dir(self) -> Path:
        return self.base / "memory"

    @property
    def journal_dir(self) -> Path:
        return self.memory_dir / "journal"

    @property
    def index_dir(self) -> Path:
        return self.base / ".index"

    @property
    def index_db(self) -> Path:
        return self.index_dir / "torsor.db"

    def journal_file(self, date_str: str) -> Path:
        return self.journal_dir / f"{date_str}.md"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_paths.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/paths.py tests/test_paths.py
git commit -m "feat: TorsorPaths layout resolver"
```

---

### Task 4: Token budget helpers

**Files:**
- Create: `src/torsor_helper/budget.py`
- Create: `tests/test_budget.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_budget.py
from torsor_helper.budget import estimate_tokens, truncate_to_tokens


def test_estimate_tokens_uses_chars_per_token():
    assert estimate_tokens("a" * 40, chars_per_token=4) == 10
    assert estimate_tokens("", chars_per_token=4) == 0


def test_truncate_keeps_short_text():
    assert truncate_to_tokens("hello", max_tokens=100, chars_per_token=4) == "hello"


def test_truncate_cuts_long_text_and_marks_it():
    text = "x" * 400  # 100 tokens at cpt=4
    out = truncate_to_tokens(text, max_tokens=10, chars_per_token=4)
    assert out.endswith("…[truncated]")
    assert len(out) <= 40 + len("…[truncated]")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_budget.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.budget'`

- [ ] **Step 3: Write the implementation**

```python
# src/torsor_helper/budget.py
from __future__ import annotations

_MARKER = "…[truncated]"


def estimate_tokens(text: str, chars_per_token: int = 4) -> int:
    if chars_per_token <= 0:
        chars_per_token = 4
    return len(text) // chars_per_token


def truncate_to_tokens(text: str, max_tokens: int, chars_per_token: int = 4) -> str:
    max_chars = max(0, max_tokens) * chars_per_token
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + _MARKER
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_budget.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/budget.py tests/test_budget.py
git commit -m "feat: token budget helpers"
```

---

### Task 5: Configuration (torsor.toml)

**Files:**
- Create: `src/torsor_helper/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from pathlib import Path

from torsor_helper.config import TorsorConfig, load_config, save_config
from torsor_helper.paths import TorsorPaths


def test_defaults_when_no_file(tmp_path: Path):
    cfg = load_config(TorsorPaths(tmp_path))
    assert cfg.version == 1
    assert cfg.budgets.bootstrap_tokens == 2000
    assert cfg.budgets.recall_tokens == 1500
    assert cfg.budgets.chars_per_token == 4
    assert cfg.embeddings.provider == "fastembed"


def test_save_then_load_round_trips(tmp_path: Path):
    paths = TorsorPaths(tmp_path)
    paths.base.mkdir(parents=True)
    cfg = TorsorConfig()
    cfg.budgets.bootstrap_tokens = 3333
    save_config(paths, cfg)
    assert paths.config_file.exists()
    loaded = load_config(paths)
    assert loaded.budgets.bootstrap_tokens == 3333
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.config'`

- [ ] **Step 3: Write the implementation**

```python
# src/torsor_helper/config.py
from __future__ import annotations

import tomllib

import tomli_w
from pydantic import BaseModel, Field

from torsor_helper.paths import TorsorPaths


class BudgetConfig(BaseModel):
    bootstrap_tokens: int = 2000
    recall_tokens: int = 1500
    chars_per_token: int = 4


class EmbeddingConfig(BaseModel):
    # Placeholder for Phase 2; unused in Phase 1.
    provider: str = "fastembed"
    model: str = "BAAI/bge-small-en-v1.5"


class TorsorConfig(BaseModel):
    version: int = 1
    budgets: BudgetConfig = Field(default_factory=BudgetConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)


def load_config(paths: TorsorPaths) -> TorsorConfig:
    if not paths.config_file.exists():
        return TorsorConfig()
    with paths.config_file.open("rb") as fh:
        data = tomllib.load(fh)
    return TorsorConfig.model_validate(data)


def save_config(paths: TorsorPaths, config: TorsorConfig) -> None:
    paths.base.mkdir(parents=True, exist_ok=True)
    with paths.config_file.open("wb") as fh:
        tomli_w.dump(config.model_dump(), fh)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/config.py tests/test_config.py
git commit -m "feat: torsor.toml config load/save"
```

---

### Task 6: Seed templates

**Files:**
- Create: `src/torsor_helper/templates.py`
- Create: `tests/test_templates.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_templates.py
from pathlib import Path

from torsor_helper.paths import TorsorPaths
from torsor_helper.templates import seed_files


def test_seed_files_cover_every_tier(tmp_path: Path):
    paths = TorsorPaths(tmp_path)
    files = seed_files(paths)
    # Every seeded file targets a path under .torsor and carries frontmatter.
    assert paths.charter in files
    assert paths.system_patterns in files
    assert paths.tech_context in files
    assert paths.active_context in files
    assert paths.progress in files
    assert paths.map_overview in files
    first_adr = paths.decisions_dir / "0001-adopt-torsor-helper.md"
    assert first_adr in files
    for path, content in files.items():
        assert content.startswith("---\n"), f"{path} missing frontmatter"
        assert "# " in content, f"{path} missing H1 title"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_templates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.templates'`

- [ ] **Step 3: Write the implementation**

```python
# src/torsor_helper/templates.py
from __future__ import annotations

from pathlib import Path

from torsor_helper.paths import TorsorPaths

CHARTER = """---
type: charter
status: active
tags: [charter]
---

# Project Charter

## What we are building
_Describe the product in 2-3 sentences._

## Why it exists
_The problem being solved and for whom._

## Non-negotiable principles
- _e.g. local-first; Markdown is the source of truth._
"""

SYSTEM_PATTERNS = """---
type: system-patterns
status: active
tags: [architecture]
---

# System Patterns

## Architecture overview
_Layers, modules, how they communicate._

## Conventions
_Naming, error handling, testing style._

## Patterns in use
- _e.g. thin MCP adapter over a tested operations layer._
"""

TECH_CONTEXT = """---
type: tech-context
status: active
tags: [architecture]
---

# Tech Context

## Stack & versions
_Languages, frameworks, runtime versions._

## Constraints
_Hard limits: deps, platforms, performance._
"""

FIRST_ADR = """---
type: decision
status: accepted
tags: [adr]
links: []
rules: []
---

# ADR 0001: Adopt torsor-helper

## Context
This project uses torsor-helper to persist architectural intent and memory.

## Decision
Markdown under `.torsor/` is the source of truth; the index is derived and disposable.

## Consequences
Memory is git-versioned and human-editable. Future ADRs may add machine-readable
`rules:` in frontmatter that the drift guard enforces (Phase 4).
"""

ACTIVE_CONTEXT = """---
type: active-context
status: active
tags: [active]
---

# Active Context

## Current focus
_What we are working on right now._

## Recent changes
_What just happened._

## Open questions
_Unresolved decisions._
"""

PROGRESS = """---
type: progress
status: active
tags: [active]
---

# Progress

## Done
## In progress
## Blocked
"""

MAP_OVERVIEW = """---
type: map
status: derived
tags: [map]
---

# Repository Map

_This file is regenerated by `torsor map` (Phase 3). Placeholder for now._
"""


def seed_files(paths: TorsorPaths) -> dict[Path, str]:
    """Return the mapping of file path -> seed content for `init` scaffolding."""
    return {
        paths.charter: CHARTER,
        paths.system_patterns: SYSTEM_PATTERNS,
        paths.tech_context: TECH_CONTEXT,
        paths.decisions_dir / "0001-adopt-torsor-helper.md": FIRST_ADR,
        paths.map_overview: MAP_OVERVIEW,
        paths.active_context: ACTIVE_CONTEXT,
        paths.progress: PROGRESS,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_templates.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/templates.py tests/test_templates.py
git commit -m "feat: seed Markdown templates for the pyramid"
```

---

### Task 7: Store — parsing helpers (frontmatter, wikilinks, hash, tier)

**Files:**
- Create: `src/torsor_helper/store.py`
- Create: `tests/conftest.py`
- Create: `tests/test_store_parsing.py`

- [ ] **Step 1: Write the shared fixture and the failing test**

```python
# tests/conftest.py
from datetime import datetime

import pytest

FIXED_CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


@pytest.fixture
def tmp_project(tmp_path):
    """A fresh project root with a scaffolded .torsor/ and a fixed clock Store."""
    from torsor_helper.paths import TorsorPaths
    from torsor_helper.store import Store

    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=FIXED_CLOCK)
    store.scaffold()
    return tmp_path
```

```python
# tests/test_store_parsing.py
from torsor_helper.models import Frontmatter, Tier
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def test_parse_frontmatter_splits_meta_and_body():
    text = "---\ntype: charter\ntags: [a, b]\n---\n\n# Title\n\nBody line\n"
    fm, body = Store.parse_frontmatter(text)
    assert fm.type == "charter"
    assert fm.tags == ["a", "b"]
    assert body.strip().startswith("# Title")


def test_parse_frontmatter_without_meta_defaults_type_note():
    fm, body = Store.parse_frontmatter("# Just a title\n\ntext")
    assert fm.type == "note"
    assert body.strip().startswith("# Just a title")


def test_extract_wikilinks_dedupes_in_order():
    assert Store.extract_wikilinks("see [[alpha]] and [[beta]] and [[alpha]]") == ["alpha", "beta"]


def test_content_hash_is_stable_and_distinct():
    assert Store.content_hash("abc") == Store.content_hash("abc")
    assert Store.content_hash("abc") != Store.content_hash("abd")


def test_serialize_round_trips_through_parse():
    text = Store.serialize(Frontmatter(type="journal"), "Hello", "World body")
    fm, body = Store.parse_frontmatter(text)
    assert fm.type == "journal"
    assert "# Hello" in body and "World body" in body


def test_tier_for_path(tmp_path):
    paths = TorsorPaths(tmp_path)
    assert Store.tier_for_path(paths, paths.charter) is Tier.CHARTER
    assert Store.tier_for_path(paths, paths.system_patterns) is Tier.ARCHITECTURE
    assert Store.tier_for_path(paths, paths.map_overview) is Tier.MAP
    assert Store.tier_for_path(paths, paths.active_context) is Tier.ACTIVE
    assert Store.tier_for_path(paths, paths.journal_file("2026-06-01")) is Tier.EPISODIC
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_store_parsing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.store'`

- [ ] **Step 3: Write the implementation (parsing helpers only; methods added next task)**

```python
# src/torsor_helper/store.py
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator

import yaml

from torsor_helper.models import Frontmatter, Note, Tier
from torsor_helper.paths import TorsorPaths

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_FM_BLOCK = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
_H1 = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


class Store:
    def __init__(
        self,
        paths: TorsorPaths,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.paths = paths
        self.clock = clock

    # ---- static parsing helpers ----
    @staticmethod
    def parse_frontmatter(text: str) -> tuple[Frontmatter, str]:
        match = _FM_BLOCK.match(text)
        if not match:
            return Frontmatter(type="note"), text
        meta = yaml.safe_load(match.group(1)) or {}
        if "type" not in meta:
            meta["type"] = "note"
        return Frontmatter.model_validate(meta), match.group(2)

    @staticmethod
    def serialize(frontmatter: Frontmatter, title: str, body: str) -> str:
        meta = frontmatter.model_dump(exclude_none=True)
        yaml_block = yaml.safe_dump(meta, sort_keys=False, default_flow_style=False).strip()
        return f"---\n{yaml_block}\n---\n\n# {title}\n\n{body.strip()}\n"

    @staticmethod
    def extract_wikilinks(text: str) -> list[str]:
        out: list[str] = []
        for m in _WIKILINK.finditer(text):
            link = m.group(1).strip()
            if link and link not in out:
                out.append(link)
        return out

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def tier_for_path(paths: TorsorPaths, path: Path) -> Tier:
        p = Path(path).resolve()
        if p == paths.charter.resolve():
            return Tier.CHARTER
        if _within(p, paths.architecture_dir):
            return Tier.ARCHITECTURE
        if _within(p, paths.map_dir):
            return Tier.MAP
        if _within(p, paths.active_dir):
            return Tier.ACTIVE
        return Tier.EPISODIC


def _within(path: Path, parent: Path) -> bool:
    parent = parent.resolve()
    return path == parent or parent in path.parents
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_store_parsing.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/store.py tests/conftest.py tests/test_store_parsing.py
git commit -m "feat: Store parsing helpers (frontmatter, wikilinks, hash, tier)"
```

---

### Task 8: Store — scaffold, read/write, iterate, journal

**Files:**
- Modify: `src/torsor_helper/store.py` (add methods after the static helpers, inside `Store`)
- Create: `tests/test_store_io.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store_io.py
from datetime import datetime

from torsor_helper.models import Frontmatter, Tier
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def test_scaffold_creates_pyramid_and_gitignore(tmp_path):
    paths = TorsorPaths(tmp_path)
    Store(paths, clock=CLOCK).scaffold()
    assert paths.charter.exists()
    assert paths.system_patterns.exists()
    assert (paths.decisions_dir / "0001-adopt-torsor-helper.md").exists()
    assert paths.active_context.exists()
    assert paths.journal_dir.is_dir()
    assert (paths.base / ".gitignore").read_text().strip() == ".index/"


def test_scaffold_is_idempotent_without_force(tmp_path):
    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=CLOCK)
    store.scaffold()
    paths.charter.write_text("EDITED")
    store.scaffold()  # must not overwrite existing files
    assert paths.charter.read_text() == "EDITED"


def test_write_then_read_note(tmp_path):
    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=CLOCK)
    target = paths.memory_dir / "note.md"
    note = store.write_note(target, Frontmatter(type="observation"), "Hi", "Body here")
    assert target.exists()
    read = store.read_note(target)
    assert read.title == "Hi"
    assert "Body here" in read.body
    assert read.tier is Tier.EPISODIC
    assert read.content_hash == note.content_hash


def test_append_journal_uses_clock_date_and_kind(tmp_path):
    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=CLOCK)
    store.scaffold()
    path = store.append_journal("Learned X", kind="learning", links=["charter"])
    assert path == paths.journal_file("2026-06-01")
    text = path.read_text()
    assert "Learned X" in text
    assert "learning" in text
    assert "[[charter]]" in text
    # appending again keeps both entries in one dated file
    store.append_journal("Learned Y", kind="observation", links=[])
    assert "Learned X" in path.read_text() and "Learned Y" in path.read_text()


def test_iter_notes_skips_index_dir(tmp_path):
    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=CLOCK)
    store.scaffold()
    paths.index_dir.mkdir(parents=True, exist_ok=True)
    (paths.index_dir / "junk.md").write_text("---\ntype: x\n---\n# Junk\n")
    titles = {n.title for n in store.iter_notes()}
    assert "Project Charter" in titles
    assert "Junk" not in titles
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_store_io.py -v`
Expected: FAIL — `AttributeError: 'Store' object has no attribute 'scaffold'`

- [ ] **Step 3: Add the methods to `Store` (insert before the module-level `_within`)**

```python
    # ---- filesystem operations ----
    def scaffold(self, force: bool = False) -> None:
        from torsor_helper.templates import seed_files

        for directory in (
            self.paths.architecture_dir,
            self.paths.decisions_dir,
            self.paths.map_dir,
            self.paths.active_dir,
            self.paths.journal_dir,
            self.paths.index_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        for path, content in seed_files(self.paths).items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if force or not path.exists():
                path.write_text(content, encoding="utf-8")

        gitignore = self.paths.base / ".gitignore"
        if force or not gitignore.exists():
            gitignore.write_text(".index/\n", encoding="utf-8")

    def write_note(
        self, path: Path, frontmatter: Frontmatter, title: str, body: str
    ) -> Note:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = self.clock().isoformat(timespec="seconds")
        if frontmatter.created is None:
            frontmatter.created = stamp
        frontmatter.updated = stamp
        text = self.serialize(frontmatter, title, body)
        path.write_text(text, encoding="utf-8")
        return self.read_note(path)

    def read_note(self, path: Path) -> Note:
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        frontmatter, raw_body = self.parse_frontmatter(text)
        title, body = _split_title(raw_body, fallback=path.stem)
        return Note(
            path=path,
            tier=self.tier_for_path(self.paths, path),
            frontmatter=frontmatter,
            title=title,
            body=body,
            content_hash=self.content_hash(text),
        )

    def iter_notes(self) -> Iterator[Note]:
        if not self.paths.base.exists():
            return
        index = self.paths.index_dir.resolve()
        for md in sorted(self.paths.base.rglob("*.md")):
            if index in md.resolve().parents:
                continue
            yield self.read_note(md)

    def append_journal(self, content: str, kind: str, links: list[str]) -> Path:
        now = self.clock()
        path = self.paths.journal_file(now.strftime("%Y-%m-%d"))
        path.parent.mkdir(parents=True, exist_ok=True)
        link_text = " ".join(f"[[{link}]]" for link in links)
        entry = (
            f"\n## {now.strftime('%H:%M')} · {kind}\n\n"
            f"{content.strip()}\n"
        )
        if link_text:
            entry += f"\nLinks: {link_text}\n"
        if not path.exists():
            header = self.serialize(
                Frontmatter(type="journal", tags=["journal"]),
                f"Journal {now.strftime('%Y-%m-%d')}",
                "",
            )
            path.write_text(header, encoding="utf-8")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(entry)
        return path
```

Add these helpers at module level (next to `_within`):

```python
def _split_title(body: str, fallback: str) -> tuple[str, str]:
    """Return (title, body-without-leading-H1)."""
    match = _H1.search(body)
    if match and body[: match.start()].strip() == "":
        title = match.group(1).strip()
        rest = body[match.end():].lstrip("\n")
        return title, rest
    return fallback, body
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_store_io.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/store.py tests/test_store_io.py
git commit -m "feat: Store scaffold/read/write/iterate/journal"
```

---

### Task 9: Keyword recall (Phase-1 retrieval)

**Files:**
- Create: `src/torsor_helper/recall.py`
- Create: `tests/test_recall.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recall.py
from pathlib import Path

from torsor_helper.models import Frontmatter, Note, Tier
from torsor_helper.recall import keyword_recall


def _note(title, body, tier, name):
    return Note(
        path=Path(f"{name}.md"),
        tier=tier,
        frontmatter=Frontmatter(type="note"),
        title=title,
        body=body,
        content_hash=name,
    )


def test_recall_ranks_matches_and_skips_misses():
    notes = [
        _note("Auth", "login and auth tokens", Tier.EPISODIC, "a"),
        _note("Payments", "stripe billing", Tier.EPISODIC, "b"),
        _note("Auth design", "auth auth auth layering", Tier.ARCHITECTURE, "c"),
    ]
    res = keyword_recall(notes, "auth", limit=8)
    paths = [h.path for h in res.hits]
    assert "b.md" not in paths  # no match
    assert paths[0] == "c.md"   # higher freq * architecture weight wins
    assert res.total_tokens > 0


def test_recall_empty_query_returns_no_hits():
    notes = [_note("X", "y", Tier.EPISODIC, "x")]
    res = keyword_recall(notes, "   ", limit=8)
    assert res.hits == []


def test_recall_respects_token_budget():
    big = "auth " * 1000
    notes = [_note(f"N{i}", big, Tier.EPISODIC, f"n{i}") for i in range(10)]
    res = keyword_recall(notes, "auth", limit=10, max_tokens=50, chars_per_token=4)
    assert res.total_tokens <= 50 or len(res.hits) == 1


def test_recall_is_deterministic():
    notes = [
        _note("A", "auth", Tier.EPISODIC, "a"),
        _note("B", "auth", Tier.EPISODIC, "b"),
    ]
    first = keyword_recall(notes, "auth")
    second = keyword_recall(notes, "auth")
    assert [h.path for h in first.hits] == [h.path for h in second.hits]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_recall.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.recall'`

- [ ] **Step 3: Write the implementation**

```python
# src/torsor_helper/recall.py
from __future__ import annotations

import re

from torsor_helper.budget import estimate_tokens
from torsor_helper.models import Note, RecallHit, RecallResult, Tier

_WORD = re.compile(r"\w+")

_DEFAULT_TIER_WEIGHTS = {
    Tier.CHARTER: 1.5,
    Tier.ARCHITECTURE: 1.4,
    Tier.ACTIVE: 1.2,
    Tier.MAP: 1.1,
    Tier.EPISODIC: 1.0,
}


def _snippet(body: str, terms: list[str], width: int = 240) -> str:
    lowered = body.lower()
    pos = min((lowered.find(t) for t in terms if t in lowered), default=-1)
    if pos < 0:
        return body[:width].strip()
    start = max(0, pos - width // 4)
    return body[start : start + width].strip()


def keyword_recall(
    notes: list[Note],
    query: str,
    limit: int = 8,
    chars_per_token: int = 4,
    max_tokens: int = 1500,
    tier_weights: dict[Tier, float] | None = None,
) -> RecallResult:
    weights = tier_weights or _DEFAULT_TIER_WEIGHTS
    terms = [t for t in _WORD.findall(query.lower()) if t]
    if not terms:
        return RecallResult(query=query, hits=[], total_tokens=0)

    scored: list[RecallHit] = []
    for note in notes:
        haystack = f"{note.title}\n{note.body}".lower()
        raw = sum(haystack.count(term) for term in terms)
        if raw == 0:
            continue
        score = raw * weights.get(note.tier, 1.0)
        scored.append(
            RecallHit(
                path=str(note.path),
                title=note.title,
                tier=note.tier,
                score=score,
                snippet=_snippet(note.body, terms),
            )
        )

    scored.sort(key=lambda h: (-h.score, h.path))

    selected: list[RecallHit] = []
    used = 0
    for hit in scored[:limit]:
        cost = estimate_tokens(hit.snippet, chars_per_token)
        if selected and used + cost > max_tokens:
            break
        selected.append(hit)
        used += cost
    return RecallResult(query=query, hits=selected, total_tokens=used)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_recall.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/recall.py tests/test_recall.py
git commit -m "feat: deterministic keyword recall (Phase 1)"
```

---

### Task 10: Operations layer (the tool behaviors)

**Files:**
- Create: `src/torsor_helper/operations.py`
- Create: `tests/test_operations.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_operations.py
from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_bootstrap_includes_all_tiers(tmp_path):
    store = _store(tmp_path)
    out = ops.bootstrap_session(store, TorsorConfig())
    assert "## Charter" in out
    assert "## System Patterns" in out
    assert "## Active Context" in out
    assert "## Progress" in out


def test_bootstrap_respects_total_budget(tmp_path):
    store = _store(tmp_path)
    cfg = TorsorConfig()
    cfg.budgets.bootstrap_tokens = 40  # tiny
    out = ops.bootstrap_session(store, cfg)
    # 40 tokens * 4 chars + section headers/markers stays small
    assert len(out) < 1200


def test_remember_appends_journal_and_recall_finds_it(tmp_path):
    store = _store(tmp_path)
    path = ops.remember(store, "We chose SQLite for the index", kind="decision", links=["tech-context"])
    assert path.endswith("2026-06-01.md")
    res = ops.recall(store, TorsorConfig(), "SQLite")
    assert any("SQLite" in h.snippet for h in res.hits)


def test_update_active_rewrites_context_and_progress(tmp_path):
    store = _store(tmp_path)
    ops.update_active(store, focus="Build Phase 1", progress="Tasks 1-9 done", open_questions="None")
    ctx = store.paths.active_context.read_text()
    prog = store.paths.progress.read_text()
    assert "Build Phase 1" in ctx
    assert "None" in ctx
    assert "Tasks 1-9 done" in prog


def test_record_handoff_is_recallable_next_session(tmp_path):
    store = _store(tmp_path)
    ops.record_handoff(
        store,
        summary="Finished store + recall",
        decisions="Markdown is source of truth",
        open_questions="vector backend?",
        next_steps="start Phase 2 indexer",
    )
    # bootstrap pulls recent journal, so the handoff resurfaces next session
    out = ops.bootstrap_session(store, TorsorConfig())
    assert "Finished store + recall" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_operations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.operations'`

- [ ] **Step 3: Write the implementation**

```python
# src/torsor_helper/operations.py
from __future__ import annotations

from torsor_helper.budget import truncate_to_tokens
from torsor_helper.config import TorsorConfig
from torsor_helper.models import Frontmatter, RecallResult
from torsor_helper.recall import keyword_recall
from torsor_helper.store import Store

# Fractions of the bootstrap budget allocated per section (must sum to <= 1.0).
_BOOTSTRAP_ALLOC = [
    ("Charter", "charter", 0.30),
    ("System Patterns", "system_patterns", 0.20),
    ("Tech Context", "tech_context", 0.15),
    ("Active Context", "active_context", 0.18),
    ("Progress", "progress", 0.10),
]
_RECENT_JOURNAL_FRACTION = 0.07


def bootstrap_session(store: Store, config: TorsorConfig) -> str:
    cpt = config.budgets.chars_per_token
    total = config.budgets.bootstrap_tokens
    sections: list[str] = []

    for label, attr, frac in _BOOTSTRAP_ALLOC:
        path = getattr(store.paths, attr)
        if not path.exists():
            continue
        note = store.read_note(path)
        text = truncate_to_tokens(note.body.strip(), int(total * frac), cpt)
        if text.strip():
            sections.append(f"## {label}\n\n{text}")

    recent = _recent_journal(store, int(total * _RECENT_JOURNAL_FRACTION), cpt)
    if recent:
        sections.append(f"## Recent Memory\n\n{recent}")

    return "\n\n".join(sections)


def _recent_journal(store: Store, max_tokens: int, cpt: int) -> str:
    journals = sorted(store.paths.journal_dir.glob("*.md")) if store.paths.journal_dir.exists() else []
    if not journals:
        return ""
    latest = store.read_note(journals[-1])
    return truncate_to_tokens(latest.body.strip(), max_tokens, cpt)


def recall(store: Store, config: TorsorConfig, query: str, limit: int = 8) -> RecallResult:
    notes = list(store.iter_notes())
    return keyword_recall(
        notes,
        query,
        limit=limit,
        chars_per_token=config.budgets.chars_per_token,
        max_tokens=config.budgets.recall_tokens,
    )


def remember(store: Store, content: str, kind: str = "observation", links: list[str] | None = None) -> str:
    path = store.append_journal(content, kind=kind, links=links or [])
    return str(path)


def update_active(store: Store, focus: str, progress: str, open_questions: str) -> None:
    store.write_note(
        store.paths.active_context,
        Frontmatter(type="active-context", tags=["active"]),
        "Active Context",
        f"## Current focus\n{focus}\n\n## Open questions\n{open_questions}\n",
    )
    store.write_note(
        store.paths.progress,
        Frontmatter(type="progress", tags=["active"]),
        "Progress",
        f"{progress}\n",
    )


def record_handoff(
    store: Store,
    summary: str,
    decisions: str = "",
    open_questions: str = "",
    next_steps: str = "",
) -> str:
    body = (
        f"**Summary:** {summary}\n\n"
        f"**Decisions:** {decisions or '—'}\n\n"
        f"**Open questions:** {open_questions or '—'}\n\n"
        f"**Next steps:** {next_steps or '—'}"
    )
    path = store.append_journal(body, kind="handoff", links=[])
    return str(path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_operations.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/operations.py tests/test_operations.py
git commit -m "feat: operations layer (bootstrap/recall/remember/update_active/handoff)"
```

---

### Task 11: MCP client config snippets

**Files:**
- Create: `src/torsor_helper/clients.py`
- Create: `tests/test_clients.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_clients.py
import json

import pytest

from torsor_helper.clients import SUPPORTED_CLIENTS, config_snippet


def test_supported_clients_present():
    for key in ("claude-code", "claude-desktop", "cursor", "windsurf", "vscode", "codex", "gemini"):
        assert key in SUPPORTED_CLIENTS


def test_claude_code_snippet_is_a_command():
    snippet = config_snippet("claude-code", root="/proj")
    assert "claude mcp add" in snippet
    assert "torsor" in snippet
    assert "/proj" in snippet


def test_cursor_snippet_is_valid_json_with_server():
    snippet = config_snippet("cursor", root="/proj")
    data = json.loads(snippet)
    assert "torsor-helper" in data["mcpServers"]
    assert data["mcpServers"]["torsor-helper"]["command"] == "torsor"
    assert "/proj" in data["mcpServers"]["torsor-helper"]["args"]


def test_unknown_client_raises():
    with pytest.raises(KeyError):
        config_snippet("nope", root="/proj")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_clients.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.clients'`

- [ ] **Step 3: Write the implementation**

```python
# src/torsor_helper/clients.py
from __future__ import annotations

import json

# Human-readable label per supported client key.
SUPPORTED_CLIENTS: dict[str, str] = {
    "claude-code": "Claude Code",
    "claude-desktop": "Claude Desktop",
    "cursor": "Cursor",
    "windsurf": "Windsurf",
    "vscode": "VS Code / Copilot",
    "codex": "Codex",
    "gemini": "Gemini CLI",
    "cline": "Cline",
    "roo": "Roo Code",
    "trae": "Trae",
    "kiro": "Kiro",
    "warp": "Warp",
}

# Clients that consume a JSON mcpServers block (file location differs per app).
_JSON_CLIENTS = {"claude-desktop", "cursor", "windsurf", "vscode", "codex", "gemini", "cline", "roo", "trae", "kiro", "warp"}


def config_snippet(client: str, root: str) -> str:
    if client not in SUPPORTED_CLIENTS:
        raise KeyError(client)
    if client == "claude-code":
        return f'claude mcp add torsor-helper -- torsor mcp --root "{root}"'
    block = {
        "mcpServers": {
            "torsor-helper": {
                "command": "torsor",
                "args": ["mcp", "--root", root],
            }
        }
    }
    return json.dumps(block, indent=2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_clients.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/clients.py tests/test_clients.py
git commit -m "feat: MCP client config snippets"
```

---

### Task 12: FastMCP server adapter

**Files:**
- Create: `src/torsor_helper/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server.py
import anyio

from torsor_helper.server import build_server


def test_server_registers_expected_tools(tmp_path):
    server = build_server(tmp_path)
    assert server.name == "torsor-helper"
    tools = anyio.run(server.list_tools)
    names = {t.name for t in tools}
    assert {"bootstrap_session", "recall", "remember", "update_active", "handoff"} <= names


def test_server_resources_registered(tmp_path):
    server = build_server(tmp_path)
    resources = anyio.run(server.list_resources)
    uris = {str(r.uri) for r in resources}
    assert any(u.startswith("torsor://") for u in uris)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.server'`

- [ ] **Step 3: Write the implementation**

```python
# src/torsor_helper/server.py
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from torsor_helper import operations as ops
from torsor_helper.config import load_config
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def build_server(root: Path | str) -> FastMCP:
    paths = TorsorPaths(Path(root))
    store = Store(paths)
    config = load_config(paths)

    mcp = FastMCP("torsor-helper")

    @mcp.tool()
    def bootstrap_session() -> str:
        """Return a budgeted summary of the whole pyramid for session start."""
        return ops.bootstrap_session(store, config)

    @mcp.tool()
    def recall(query: str, limit: int = 8) -> str:
        """Hybrid keyword search across memory, wiki and map. Returns ranked snippets."""
        result = ops.recall(store, config, query, limit=limit)
        if not result.hits:
            return f"No matches for: {query!r}"
        lines = [f"### {h.title} ({h.tier.name})\n{h.snippet}" for h in result.hits]
        return "\n\n".join(lines)

    @mcp.tool()
    def remember(content: str, kind: str = "observation", links: list[str] | None = None) -> str:
        """Persist an observation/decision/learning to episodic memory."""
        return ops.remember(store, content, kind=kind, links=links)

    @mcp.tool()
    def update_active(focus: str, progress: str, open_questions: str) -> str:
        """Update the active working state (current focus, progress, open questions)."""
        ops.update_active(store, focus, progress, open_questions)
        return "active context updated"

    @mcp.tool()
    def handoff(summary: str, decisions: str = "", open_questions: str = "", next_steps: str = "") -> str:
        """Write a structured end-of-session handoff that the next session resumes from."""
        return ops.record_handoff(store, summary, decisions, open_questions, next_steps)

    @mcp.resource("torsor://charter")
    def charter_resource() -> str:
        return paths.charter.read_text(encoding="utf-8") if paths.charter.exists() else ""

    @mcp.resource("torsor://active")
    def active_resource() -> str:
        return paths.active_context.read_text(encoding="utf-8") if paths.active_context.exists() else ""

    return mcp


def run(root: Path | str) -> None:
    build_server(root).run()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server.py -v`
Expected: PASS (2 passed)

> If `server.list_tools` / `server.list_resources` are not awaitable coroutine methods in the installed `mcp` version, replace the body with `tools = server._tool_manager.list_tools()` (synchronous) and assert on `t.name`. The behavior under test (tool registration) is unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/server.py tests/test_server.py
git commit -m "feat: FastMCP server adapter wiring tools + resources"
```

---

### Task 13: Typer CLI (`init` / `mcp` / `doctor`) + end-to-end test

**Files:**
- Create: `src/torsor_helper/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.paths import TorsorPaths

runner = CliRunner()


def test_init_scaffolds_and_prints_client_snippet(tmp_path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path), "--client", "cursor"])
    assert result.exit_code == 0, result.output
    paths = TorsorPaths(tmp_path)
    assert paths.charter.exists()
    assert paths.config_file.exists()
    assert "mcpServers" in result.output  # cursor JSON snippet printed


def test_doctor_reports_ok_after_init(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_doctor_flags_missing_project(tmp_path):
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "not initialized" in result.output.lower()


def test_end_to_end_remember_then_bootstrap(tmp_path):
    # init, then drive operations directly to prove the loop closes
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    from datetime import datetime

    from torsor_helper import operations as ops
    from torsor_helper.config import load_config
    from torsor_helper.store import Store

    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=lambda: datetime(2026, 6, 1, 9, 30, 0))
    ops.remember(store, "Picked FastMCP", kind="decision", links=[])
    out = ops.bootstrap_session(store, load_config(paths))
    assert "Picked FastMCP" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.cli'`

- [ ] **Step 3: Write the implementation**

```python
# src/torsor_helper/cli.py
from __future__ import annotations

from pathlib import Path

import typer

from torsor_helper.clients import SUPPORTED_CLIENTS, config_snippet
from torsor_helper.config import TorsorConfig, load_config, save_config
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

app = typer.Typer(help="torsor-helper: persistent memory + architectural intent over MCP.")


@app.command()
def init(
    root: Path = typer.Option(Path("."), help="Project root to scaffold .torsor/ in."),
    client: str | None = typer.Option(None, help=f"Print MCP config for: {', '.join(SUPPORTED_CLIENTS)}"),
    force: bool = typer.Option(False, help="Overwrite existing seed files."),
) -> None:
    """Scaffold the .torsor/ pyramid and write torsor.toml."""
    paths = TorsorPaths(root)
    Store(paths).scaffold(force=force)
    if not paths.config_file.exists() or force:
        save_config(paths, TorsorConfig())
    typer.echo(f"Initialized torsor-helper at {paths.base}")
    if client:
        if client not in SUPPORTED_CLIENTS:
            typer.echo(f"Unknown client {client!r}. Known: {', '.join(SUPPORTED_CLIENTS)}", err=True)
            raise typer.Exit(code=1)
        typer.echo(f"\n# MCP config for {SUPPORTED_CLIENTS[client]}:\n")
        typer.echo(config_snippet(client, root=str(root.resolve())))


@app.command()
def mcp(root: Path = typer.Option(Path("."), help="Project root containing .torsor/.")) -> None:
    """Run the torsor-helper MCP server over stdio."""
    from torsor_helper.server import run

    run(root)


@app.command()
def doctor(root: Path = typer.Option(Path("."), help="Project root to check.")) -> None:
    """Verify a torsor-helper project is healthy."""
    paths = TorsorPaths(root)
    if not paths.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    missing = [
        p.name
        for p in (paths.charter, paths.system_patterns, paths.active_context, paths.progress)
        if not p.exists()
    ]
    if missing:
        typer.echo(f"Project incomplete; missing: {', '.join(missing)}", err=True)
        raise typer.Exit(code=1)
    load_config(paths)  # raises if malformed
    typer.echo("OK: torsor-helper project is healthy.")


def main() -> None:
    app()
```

- [ ] **Step 4: Run the full suite**

Run: `pytest -v`
Expected: PASS (all tests across every module green)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/cli.py tests/test_cli.py
git commit -m "feat: Typer CLI (init/mcp/doctor) + end-to-end loop test"
```

---

### Task 14: Manual smoke test + README sync

**Files:**
- Modify: `README.md` (check the Phase 1 roadmap box; correct any command that drifted)

- [ ] **Step 1: Install and smoke-test the real binary**

```bash
pip install -e ".[dev]"
cd /tmp && rm -rf torsor-smoke && mkdir torsor-smoke && cd torsor-smoke
torsor init --client claude-code
torsor doctor
ls -R .torsor
```
Expected: `.torsor/` tree exists (charter, architecture/, active/, memory/journal/, .gitignore), a `claude mcp add ...` snippet prints, `doctor` prints `OK`.

- [ ] **Step 2: Smoke-test the server starts**

Run: `torsor mcp --root /tmp/torsor-smoke` then send EOF (Ctrl-D) / Ctrl-C.
Expected: process starts and waits on stdio without traceback. (A full MCP handshake test belongs in Phase 2 integration; here we only confirm it launches.)

- [ ] **Step 3: Tick the Phase 1 box in README**

In `README.md`, change the Phase 1 roadmap line to:
```markdown
- [x] **Phase 1 — Foundation:** pyramid scaffold, `init`, MCP server with `bootstrap_session` / `remember` / `recall` (keyword) / `update_active` / `handoff`
```
(Note: Phase 1 ships **keyword** recall; SQLite/FTS hybrid arrives in Phase 2 — keep the README accurate.)

- [ ] **Step 4: Commit and push**

```bash
git add README.md
git commit -m "docs: mark Phase 1 foundation complete"
git push
```

---

## Self-Review

**Spec coverage** (spec → task):
- Pyramid tiers + on-disk layout (§4) → Tasks 3, 6, 8 (paths, templates, scaffold)
- Markdown source of truth + frontmatter + wikilinks (§4) → Task 7
- `store` module (§5) → Tasks 7–8
- `cli` module (§5) → Task 13
- `server` module + MCP surface tools/resources (§5, §6) → Task 12
- `bootstrap_session / recall / remember / update_active / handoff` (§6) → Tasks 9, 10, 12
- Token budgeting on context-returning tools (§10) → Tasks 4, 10
- Config (`torsor.toml`) (§5, §9) → Task 5
- Platform reach / client snippets (§12) → Task 11
- Error handling: `doctor`, disposable index ignored via `.gitignore`, malformed config raises (§10) → Tasks 5, 8, 13
- TDD per module (§11) → every task
- **Deferred to later phases (intentionally not in this plan):** SQLite/`sqlite-vec`/FastEmbed + hybrid retrieval + wikilink graph index (Phase 2); tree-sitter cartographer + `get_intent` + `map_repo` (Phase 3); ADRs-as-rules + `record_decision` + `check_drift` + sampling guard (Phase 4); `consolidate` + HTTP/team mode (Phase 5). The Phase-1 `recall` is keyword-based by design; `map/overview.md` is a placeholder until Phase 3.

**Placeholder scan:** No "TBD/TODO/handle edge cases" left; every code/test step contains runnable content.

**Type consistency:** Names match the locked Interface Contracts across tasks — `Tier`, `Frontmatter`, `Note`, `RecallResult`, `Store.scaffold/read_note/write_note/iter_notes/append_journal`, `keyword_recall(...)`, `operations.{bootstrap_session,recall,remember,update_active,record_handoff}`, `config_snippet`, `build_server`. The MCP tool `handoff` maps to `operations.record_handoff` (intentional: tool name vs. function name), documented in Task 12.

## Notes for the implementer
- Run `pip install -e ".[dev]"` once before Task 2; re-run only if dependencies change.
- Keep `server.py` and `cli.py` as **thin adapters** — all behavior lives in `operations.py` / `store.py`, which is why those have the heavy test coverage.
- The index directory (`.torsor/.index/`) is created but unused in Phase 1; it exists so `.gitignore` and `iter_notes` skip logic are correct before Phase 2 lands.
