# torsor-helper Phase 2 (Index) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Phase-1 keyword recall with a real derived index — SQLite (FTS5 + a wiki-link edge graph) plus local embeddings stored as float32 BLOBs with NumPy cosine search — and fuse them into hybrid retrieval, while leaving the Coach (Phase 6) hooks in place.

**Architecture:** Markdown stays the source of truth. A disposable `.torsor/.index/torsor.db` is built incrementally from the notes (content-hash diff). Retrieval fuses a vector ranking (NumPy cosine over stored embeddings) and an FTS5/BM25 ranking via Reciprocal Rank Fusion (RRF), then applies tier weights + recency + a 1-hop wiki-link graph boost, filtered by note `type`/`kind` and token-budgeted. `operations.recall` uses the index when available and falls back to Phase-1 keyword recall otherwise.

**Tech Stack:** Python ≥3.11, stdlib `sqlite3` (FTS5), `numpy` (cosine), optional `fastembed` extra (else a deterministic `HashingEmbedder`); builds on Phase-1 `store`/`config`/`models`/`operations`.

**Key design decisions:**
- **No `sqlite-vec`** — float32 BLOB + NumPy cosine is portable everywhere and adequate for typical repo sizes; `sqlite-vec` is a future opt-in for scale.
- **`fastembed` is optional** — default embedder falls back to `HashingEmbedder` (deterministic, dependency-free) so installs stay light and the suite runs offline/fast. All tests use `HashingEmbedder`.
- **Coach hooks (Phase 6):** the index stores `type`/`kind`/`access_count`; retrieval is filterable by `type`/`kind`; `memory/insights/` is scaffolded; a thin `recommend` tool stub is registered.

---

## File Structure

```
src/torsor_helper/embeddings.py   # Embedder protocol, HashingEmbedder, FastEmbedEmbedder, get_embedder()
src/torsor_helper/db.py           # SQLite schema + connect + pack/unpack + cosine/fts/edge/meta helpers
src/torsor_helper/indexer.py      # reindex(store, conn, embedder, full) — incremental sync
src/torsor_helper/search.py       # hybrid_search(...) -> RecallResult (RRF fusion + tier/recency/graph + filter + budget)
src/torsor_helper/config.py       # MODIFY: add IndexConfig + EmbeddingConfig.dim + auto_index
src/torsor_helper/paths.py        # MODIFY: add insights_dir
src/torsor_helper/store.py        # MODIFY: scaffold creates memory/insights/
src/torsor_helper/operations.py   # MODIFY: recall() uses index w/ keyword fallback
src/torsor_helper/server.py       # MODIFY: register thin `recommend` stub tool
src/torsor_helper/cli.py          # MODIFY: add `torsor index` command; doctor reports index status
pyproject.toml                    # MODIFY: numpy dep + [embeddings] extra
tests/test_embeddings.py
tests/test_db.py
tests/test_indexer.py
tests/test_search.py
tests/test_index_integration.py   # recall-via-index + fallback + coach hooks
```

## Interface contracts (locked — use these exact names)

- `embeddings.Embedder` (Protocol): attrs `name: str`, `dim: int`; method `embed(texts: Sequence[str]) -> list[list[float]]`.
- `embeddings.HashingEmbedder(dim: int = 384)`; `embeddings.FastEmbedEmbedder(model: str)`; `embeddings.get_embedder(config) -> Embedder`.
- `db.connect(path: Path) -> sqlite3.Connection`; `db.SCHEMA_VERSION: int`.
- `db.pack(vec: Sequence[float]) -> bytes`; `db.unpack(blob: bytes) -> "np.ndarray"`.
- `db.note_hashes(conn) -> dict[str, str]`; `db.upsert_note(conn, path, content_hash, tier, type_, kind, title, updated)`; `db.replace_fts(conn, path, title, body)`; `db.replace_edges(conn, src, slugs)`; `db.upsert_vector(conn, path, vec)`; `db.delete_note(conn, path)`.
- `db.cosine_search(conn, qvec, limit) -> list[tuple[str, float]]`; `db.fts_search(conn, query, limit) -> list[tuple[str, float]]`; `db.note_row(conn, path) -> dict | None`; `db.body_of(conn, path) -> str`; `db.neighbors(conn, path) -> list[str]`; `db.bump_access(conn, paths)`.
- `indexer.reindex(store, conn, embedder, *, full: bool = False) -> dict` (stats: `{"indexed", "deleted", "total"}`).
- `search.hybrid_search(conn, embedder, config, query, *, limit=8, max_tokens=1500, type_=None, kind=None) -> RecallResult`.
- `config`: `EmbeddingConfig.dim: int = 384`; `IndexConfig(rrf_k=60, recency_weight=0.1, graph_boost=0.1, auto_index=True)`; `TorsorConfig.index: IndexConfig`.

---

### Task 1: Dependencies + config additions

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/torsor_helper/config.py`
- Create: `tests/test_config_index.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config_index.py
from torsor_helper.config import TorsorConfig


def test_index_config_defaults():
    cfg = TorsorConfig()
    assert cfg.index.rrf_k == 60
    assert cfg.index.recency_weight == 0.1
    assert cfg.index.graph_boost == 0.1
    assert cfg.index.auto_index is True
    assert cfg.embeddings.dim == 384
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_config_index.py -v`
Expected: FAIL — `AttributeError: 'TorsorConfig' object has no attribute 'index'`

- [ ] **Step 3: Implement**

In `pyproject.toml`, add `numpy>=1.26` to `[project] dependencies` and a new optional extra:
```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "anyio>=4.0"]
embeddings = ["fastembed>=0.3"]
```

In `src/torsor_helper/config.py`, add `dim` to `EmbeddingConfig`, add `IndexConfig`, and wire it into `TorsorConfig`:
```python
class EmbeddingConfig(BaseModel):
    provider: str = "fastembed"
    model: str = "BAAI/bge-small-en-v1.5"
    dim: int = 384


class IndexConfig(BaseModel):
    rrf_k: int = 60
    recency_weight: float = 0.1
    graph_boost: float = 0.1
    auto_index: bool = True
```
And in `TorsorConfig` add the field:
```python
    index: IndexConfig = Field(default_factory=IndexConfig)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_config_index.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/torsor_helper/config.py tests/test_config_index.py
git commit -m "feat: index + embedding config and numpy dep"
```

---

### Task 2: Embeddings (protocol + deterministic HashingEmbedder + FastEmbed fallback)

**Files:**
- Create: `src/torsor_helper/embeddings.py`
- Create: `tests/test_embeddings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_embeddings.py
import math

from torsor_helper.config import TorsorConfig
from torsor_helper.embeddings import HashingEmbedder, get_embedder


def test_hashing_embedder_is_deterministic_and_normalized():
    e = HashingEmbedder(dim=64)
    a = e.embed(["auth tokens and login"])[0]
    b = e.embed(["auth tokens and login"])[0]
    assert a == b                      # deterministic across calls
    assert len(a) == 64
    assert abs(math.sqrt(sum(x * x for x in a)) - 1.0) < 1e-6  # L2-normalized


def test_hashing_embedder_distinguishes_texts():
    e = HashingEmbedder(dim=64)
    auth = e.embed(["authentication login session"])[0]
    pay = e.embed(["stripe billing invoice"])[0]
    dot = sum(x * y for x, y in zip(auth, pay))
    assert dot < 0.9  # unrelated texts are not near-identical


def test_empty_text_yields_zero_vector():
    e = HashingEmbedder(dim=8)
    assert e.embed([""])[0] == [0.0] * 8


def test_get_embedder_falls_back_to_hashing(monkeypatch):
    # Force the fastembed path to fail -> must fall back to HashingEmbedder.
    import torsor_helper.embeddings as emb

    def boom(model):
        raise RuntimeError("no fastembed")

    monkeypatch.setattr(emb, "_make_fastembed", boom)
    cfg = TorsorConfig()
    cfg.embeddings.provider = "fastembed"
    cfg.embeddings.dim = 32
    e = get_embedder(cfg)
    assert e.name == "hashing"
    assert e.dim == 32
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_embeddings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.embeddings'`

- [ ] **Step 3: Implement**

```python
# src/torsor_helper/embeddings.py
from __future__ import annotations

import hashlib
import math
import re
import warnings
from typing import Protocol, Sequence, runtime_checkable

_WORD = re.compile(r"\w+")


@runtime_checkable
class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Deterministic, dependency-free bag-of-words hashing embedder.

    Stable across processes (uses md5, not Python's salted hash). Used in tests
    and as the fallback when fastembed is unavailable.
    """

    name = "hashing"

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in _WORD.findall(text.lower()):
                digest = hashlib.md5(token.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "big") % self.dim
                vec[idx] += 1.0
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            out.append(vec)
        return out


class FastEmbedEmbedder:
    """Local ONNX embeddings via the optional `fastembed` extra (lazy-loaded)."""

    name = "fastembed"

    def __init__(self, model: str) -> None:
        self._model = _make_fastembed(model)
        # bge-small-en-v1.5 is 384-dim; query the model to be safe.
        probe = next(iter(self._model.embed(["x"])))
        self.dim = len(list(probe))

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [list(map(float, v)) for v in self._model.embed(list(texts))]


def _make_fastembed(model: str):  # pragma: no cover - exercised only when installed
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=model)


def get_embedder(config) -> Embedder:
    if config.embeddings.provider == "fastembed":
        try:
            return FastEmbedEmbedder(config.embeddings.model)
        except Exception as exc:  # not installed / model load failed
            warnings.warn(
                f"fastembed unavailable ({exc}); falling back to HashingEmbedder. "
                "Install with `pip install torsor-helper[embeddings]` for semantic recall.",
                stacklevel=2,
            )
    return HashingEmbedder(config.embeddings.dim)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_embeddings.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/embeddings.py tests/test_embeddings.py
git commit -m "feat: embeddings (HashingEmbedder + fastembed fallback)"
```

---

### Task 3: SQLite index — schema, connection, and helpers

**Files:**
- Create: `src/torsor_helper/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db.py
import numpy as np

from torsor_helper import db


def _conn(tmp_path):
    return db.connect(tmp_path / "torsor.db")


def test_connect_creates_schema_and_version(tmp_path):
    conn = _conn(tmp_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    assert {"notes", "vectors", "edges", "meta"} <= tables
    assert int(db.meta_get(conn, "schema_version")) == db.SCHEMA_VERSION


def test_pack_unpack_roundtrip():
    vec = [0.1, -0.2, 0.3]
    out = db.unpack(db.pack(vec))
    assert np.allclose(out, np.array(vec, dtype=np.float32))


def test_upsert_note_and_hashes(tmp_path):
    conn = _conn(tmp_path)
    db.upsert_note(conn, "a.md", "h1", 4, "journal", None, "A", "2026-06-01T09:30:00")
    db.upsert_note(conn, "a.md", "h2", 4, "journal", None, "A", "2026-06-01T10:00:00")  # update
    assert db.note_hashes(conn) == {"a.md": "h2"}
    row = db.note_row(conn, "a.md")
    assert row["title"] == "A" and row["tier"] == 4 and row["access_count"] == 0


def test_fts_search_finds_terms(tmp_path):
    conn = _conn(tmp_path)
    db.upsert_note(conn, "a.md", "h", 4, "journal", None, "Auth", "t")
    db.replace_fts(conn, "a.md", "Auth", "login and auth tokens")
    db.upsert_note(conn, "b.md", "h", 4, "journal", None, "Pay", "t")
    db.replace_fts(conn, "b.md", "Pay", "stripe billing")
    hits = [p for p, _ in db.fts_search(conn, "auth", 10)]
    assert "a.md" in hits and "b.md" not in hits
    assert db.body_of(conn, "a.md") == "login and auth tokens"


def test_cosine_search_ranks_by_similarity(tmp_path):
    conn = _conn(tmp_path)
    for path, vec in [("x.md", [1.0, 0.0]), ("y.md", [0.0, 1.0]), ("z.md", [0.9, 0.1])]:
        db.upsert_note(conn, path, "h", 4, "journal", None, path, "t")
        db.upsert_vector(conn, path, vec)
    ranked = db.cosine_search(conn, [1.0, 0.0], 3)
    assert ranked[0][0] == "x.md"
    assert ranked[1][0] == "z.md"  # closer to [1,0] than [0,1]


def test_edges_and_neighbors(tmp_path):
    conn = _conn(tmp_path)
    db.upsert_note(conn, "charter.md", "h", 0, "charter", None, "Charter", "t")
    db.replace_edges(conn, "note.md", ["charter"])  # [[charter]] -> resolves by stem
    assert db.neighbors(conn, "note.md") == ["charter.md"]


def test_delete_note_removes_everywhere(tmp_path):
    conn = _conn(tmp_path)
    db.upsert_note(conn, "a.md", "h", 4, "journal", None, "A", "t")
    db.replace_fts(conn, "a.md", "A", "body")
    db.upsert_vector(conn, "a.md", [1.0, 0.0])
    db.delete_note(conn, "a.md")
    assert db.note_hashes(conn) == {}
    assert db.cosine_search(conn, [1.0, 0.0], 5) == []


def test_bump_access(tmp_path):
    conn = _conn(tmp_path)
    db.upsert_note(conn, "a.md", "h", 4, "journal", None, "A", "t")
    db.bump_access(conn, ["a.md"])
    db.bump_access(conn, ["a.md"])
    assert db.note_row(conn, "a.md")["access_count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.db'`

- [ ] **Step 3: Implement**

```python
# src/torsor_helper/db.py
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Sequence

import numpy as np

SCHEMA_VERSION = 1


def connect(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    _create_schema(conn)
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS notes (
            path TEXT PRIMARY KEY, content_hash TEXT, tier INTEGER,
            type TEXT, kind TEXT, title TEXT, updated TEXT,
            access_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS vectors (path TEXT PRIMARY KEY, dim INTEGER, embedding BLOB);
        CREATE TABLE IF NOT EXISTS edges (src TEXT, target_slug TEXT, target_path TEXT);
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(path UNINDEXED, title, body);
        """
    )
    if meta_get(conn, "schema_version") is None:
        meta_set(conn, "schema_version", str(SCHEMA_VERSION))
    conn.commit()


def meta_get(conn, key):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def meta_set(conn, key, value):
    conn.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=?", (key, value, value))


def pack(vec: Sequence[float]) -> bytes:
    return np.asarray(list(vec), dtype=np.float32).tobytes()


def unpack(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def note_hashes(conn) -> dict[str, str]:
    return {r["path"]: r["content_hash"] for r in conn.execute("SELECT path, content_hash FROM notes")}


def upsert_note(conn, path, content_hash, tier, type_, kind, title, updated):
    conn.execute(
        """INSERT INTO notes(path, content_hash, tier, type, kind, title, updated)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(path) DO UPDATE SET
             content_hash=excluded.content_hash, tier=excluded.tier, type=excluded.type,
             kind=excluded.kind, title=excluded.title, updated=excluded.updated""",
        (path, content_hash, int(tier), type_, kind, title, updated),
    )


def note_row(conn, path):
    row = conn.execute("SELECT * FROM notes WHERE path=?", (path,)).fetchone()
    return dict(row) if row else None


def replace_fts(conn, path, title, body):
    conn.execute("DELETE FROM fts WHERE path=?", (path,))
    conn.execute("INSERT INTO fts(path, title, body) VALUES(?,?,?)", (path, title, body))


def body_of(conn, path):
    row = conn.execute("SELECT body FROM fts WHERE path=?", (path,)).fetchone()
    return row["body"] if row else ""


def replace_edges(conn, src, slugs):
    conn.execute("DELETE FROM edges WHERE src=?", (src,))
    for slug in slugs:
        target = conn.execute(
            "SELECT path FROM notes WHERE path LIKE ? LIMIT 1", (f"%/{slug}.md",)
        ).fetchone()
        # also try exact stem match at any depth
        if target is None:
            target = conn.execute(
                "SELECT path FROM notes WHERE path = ? OR path LIKE ? LIMIT 1",
                (f"{slug}.md", f"%/{slug}.md"),
            ).fetchone()
        conn.execute(
            "INSERT INTO edges(src, target_slug, target_path) VALUES(?,?,?)",
            (src, slug, target["path"] if target else None),
        )


def neighbors(conn, path):
    return [r["target_path"] for r in conn.execute(
        "SELECT target_path FROM edges WHERE src=? AND target_path IS NOT NULL", (path,))]


def upsert_vector(conn, path, vec):
    blob = pack(vec)
    conn.execute(
        "INSERT INTO vectors(path, dim, embedding) VALUES(?,?,?) "
        "ON CONFLICT(path) DO UPDATE SET dim=excluded.dim, embedding=excluded.embedding",
        (path, len(vec), blob),
    )


def delete_note(conn, path):
    for tbl in ("notes", "vectors", "edges"):
        col = "src" if tbl == "edges" else "path"
        conn.execute(f"DELETE FROM {tbl} WHERE {col}=?", (path,))
    conn.execute("DELETE FROM fts WHERE path=?", (path,))


def cosine_search(conn, qvec, limit):
    rows = conn.execute("SELECT path, embedding FROM vectors").fetchall()
    if not rows:
        return []
    q = np.asarray(list(qvec), dtype=np.float32)
    qn = np.linalg.norm(q)
    if qn == 0:
        return []
    q = q / qn
    scored = []
    for r in rows:
        v = unpack(r["embedding"])
        vn = np.linalg.norm(v)
        if vn == 0:
            continue
        scored.append((r["path"], float(np.dot(q, v / vn))))
    scored.sort(key=lambda t: (-t[1], t[0]))
    return scored[:limit]


def fts_search(conn, query, limit):
    terms = [t for t in __import__("re").findall(r"\w+", query.lower()) if t]
    if not terms:
        return []
    match = " OR ".join(terms)
    rows = conn.execute(
        "SELECT path, bm25(fts) AS score FROM fts WHERE fts MATCH ? ORDER BY score LIMIT ?",
        (match, limit),
    ).fetchall()
    return [(r["path"], float(r["score"])) for r in rows]


def bump_access(conn, paths):
    conn.executemany("UPDATE notes SET access_count = access_count + 1 WHERE path=?", [(p,) for p in paths])
    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_db.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/db.py tests/test_db.py
git commit -m "feat: SQLite index schema + vector/fts/edge helpers"
```

---

### Task 4: Incremental indexer

**Files:**
- Create: `src/torsor_helper/indexer.py`
- Create: `tests/test_indexer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_indexer.py
from datetime import datetime

from torsor_helper import db
from torsor_helper.embeddings import HashingEmbedder
from torsor_helper.indexer import reindex
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _setup(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    conn = db.connect(tmp_path / "idx.db")
    return store, conn


def test_reindex_indexes_all_notes(tmp_path):
    store, conn = _setup(tmp_path)
    stats = reindex(store, conn, HashingEmbedder(dim=64))
    assert stats["indexed"] >= 6  # charter + 2 arch + adr + active + progress + map
    assert stats["total"] == stats["indexed"]
    # every indexed note has a vector and an fts row
    paths = list(db.note_hashes(conn))
    assert db.cosine_search(conn, HashingEmbedder(64).embed(["architecture"])[0], 50)


def test_reindex_is_incremental(tmp_path):
    store, conn = _setup(tmp_path)
    reindex(store, conn, HashingEmbedder(dim=64))
    # second run with no changes indexes nothing
    stats = reindex(store, conn, HashingEmbedder(dim=64))
    assert stats["indexed"] == 0
    # editing one file re-indexes exactly one
    store.paths.charter.write_text(store.paths.charter.read_text() + "\nnew line\n")
    stats = reindex(store, conn, HashingEmbedder(dim=64))
    assert stats["indexed"] == 1


def test_reindex_deletes_removed_notes(tmp_path):
    store, conn = _setup(tmp_path)
    reindex(store, conn, HashingEmbedder(dim=64))
    store.paths.tech_context.unlink()
    stats = reindex(store, conn, HashingEmbedder(dim=64))
    assert stats["deleted"] == 1
    assert str(store.paths.tech_context) not in db.note_hashes(conn)


def test_reindex_records_type_and_kind(tmp_path):
    store, conn = _setup(tmp_path)
    # a journal note carries kind via frontmatter for the Coach hook
    store.append_journal("learned X", kind="learning", links=["charter"])
    reindex(store, conn, HashingEmbedder(dim=64))
    journal = store.paths.journal_file("2026-06-01")
    row = db.note_row(conn, str(journal))
    assert row["type"] == "journal"
    # the [[charter]] wikilink became an edge
    assert db.neighbors(conn, str(journal)) == [str(store.paths.charter)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_indexer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.indexer'`

- [ ] **Step 3: Implement**

```python
# src/torsor_helper/indexer.py
from __future__ import annotations

from torsor_helper import db
from torsor_helper.store import Store


def reindex(store: Store, conn, embedder, *, full: bool = False) -> dict:
    existing = db.note_hashes(conn)
    seen: set[str] = set()
    pending: list[tuple[str, str]] = []  # (path, body) to embed

    for note in store.iter_notes():
        path = str(note.path)
        seen.add(path)
        if not full and existing.get(path) == note.content_hash:
            continue
        kind = getattr(note.frontmatter, "kind", None)
        db.upsert_note(
            conn, path, note.content_hash, int(note.tier),
            note.frontmatter.type, kind, note.title, note.frontmatter.updated or "",
        )
        db.replace_fts(conn, path, note.title, note.body)
        db.replace_edges(conn, path, store.extract_wikilinks(note.body))
        pending.append((path, note.body))

    if pending:
        vectors = embedder.embed([body for _, body in pending])
        for (path, _), vec in zip(pending, vectors):
            db.upsert_vector(conn, path, vec)

    deleted = 0
    for path in list(existing):
        if path not in seen:
            db.delete_note(conn, path)
            deleted += 1

    conn.commit()
    return {"indexed": len(pending), "deleted": deleted, "total": len(seen)}
```

> Note: `replace_edges` resolves wiki-link slugs against the `notes` table, so links to a note indexed *later in the same pass* may resolve on the next `reindex`. That's acceptable (the graph converges); a forward-reference is simply re-resolved when either file next changes.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_indexer.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/indexer.py tests/test_indexer.py
git commit -m "feat: incremental indexer (hash-diff, vectors, fts, edges)"
```

---

### Task 5: Hybrid retriever (RRF fusion)

**Files:**
- Create: `src/torsor_helper/search.py`
- Create: `tests/test_search.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_search.py
from datetime import datetime

from torsor_helper import db
from torsor_helper.config import TorsorConfig
from torsor_helper.embeddings import HashingEmbedder
from torsor_helper.indexer import reindex
from torsor_helper.paths import TorsorPaths
from torsor_helper.search import hybrid_search
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _indexed(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    store.append_journal("We chose SQLite for the derived index", kind="decision", links=[])
    conn = db.connect(tmp_path / "idx.db")
    reindex(store, conn, HashingEmbedder(dim=128))
    return store, conn


def test_hybrid_search_finds_relevant_note(tmp_path):
    store, conn = _indexed(tmp_path)
    res = hybrid_search(conn, HashingEmbedder(dim=128), TorsorConfig(), "SQLite index")
    assert res.hits
    assert any("SQLite" in h.snippet for h in res.hits)


def test_hybrid_search_empty_query_returns_nothing(tmp_path):
    store, conn = _indexed(tmp_path)
    res = hybrid_search(conn, HashingEmbedder(dim=128), TorsorConfig(), "   ")
    assert res.hits == []


def test_hybrid_search_filter_by_type(tmp_path):
    store, conn = _indexed(tmp_path)
    res = hybrid_search(conn, HashingEmbedder(dim=128), TorsorConfig(), "SQLite", type_="journal")
    assert res.hits
    assert all(h.tier.name == "EPISODIC" for h in res.hits)  # journals are episodic


def test_hybrid_search_bumps_access_count(tmp_path):
    store, conn = _indexed(tmp_path)
    res = hybrid_search(conn, HashingEmbedder(dim=128), TorsorConfig(), "SQLite")
    top = res.hits[0].path
    assert db.note_row(conn, top)["access_count"] >= 1


def test_hybrid_search_is_deterministic(tmp_path):
    store, conn = _indexed(tmp_path)
    e = HashingEmbedder(dim=128)
    a = hybrid_search(conn, e, TorsorConfig(), "architecture")
    b = hybrid_search(conn, e, TorsorConfig(), "architecture")
    assert [h.path for h in a.hits] == [h.path for h in b.hits]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'torsor_helper.search'`

- [ ] **Step 3: Implement**

```python
# src/torsor_helper/search.py
from __future__ import annotations

import re

from torsor_helper import db
from torsor_helper.budget import estimate_tokens
from torsor_helper.models import RecallHit, RecallResult, Tier

_WORD = re.compile(r"\w+")
_TIER_WEIGHTS = {
    Tier.CHARTER: 1.5, Tier.ARCHITECTURE: 1.4, Tier.ACTIVE: 1.2, Tier.MAP: 1.1, Tier.EPISODIC: 1.0,
}


def _snippet(body: str, terms: list[str], width: int = 240) -> str:
    low = body.lower()
    pos = min((low.find(t) for t in terms if t in low), default=-1)
    if pos < 0:
        return body[:width].strip()
    start = max(0, pos - width // 4)
    return body[start : start + width].strip()


def hybrid_search(conn, embedder, config, query, *, limit=8, max_tokens=1500, type_=None, kind=None) -> RecallResult:
    terms = [t for t in _WORD.findall(query.lower()) if t]
    if not terms:
        return RecallResult(query=query, hits=[], total_tokens=0)

    k = config.index.rrf_k
    pool = max(limit * 4, 20)
    qvec = embedder.embed([query])[0]
    vec_ranked = db.cosine_search(conn, qvec, pool)
    fts_ranked = db.fts_search(conn, query, pool)

    # Reciprocal Rank Fusion over the two streams.
    scores: dict[str, float] = {}
    for rank, (path, _) in enumerate(vec_ranked):
        scores[path] = scores.get(path, 0.0) + 1.0 / (k + rank)
    for rank, (path, _) in enumerate(fts_ranked):
        scores[path] = scores.get(path, 0.0) + 1.0 / (k + rank)
    if not scores:
        return RecallResult(query=query, hits=[], total_tokens=0)

    # Recency: rank candidates by `updated` desc, add a small RRF-style stream.
    rows = {p: db.note_row(conn, p) for p in scores}
    by_recency = sorted(scores, key=lambda p: (rows[p] or {}).get("updated") or "", reverse=True)
    for rank, path in enumerate(by_recency):
        scores[path] += config.index.recency_weight * (1.0 / (k + rank))

    # 1-hop graph boost from the current top candidate.
    top = max(scores, key=lambda p: scores[p])
    for nbr in db.neighbors(conn, top):
        if nbr in scores:
            scores[nbr] += config.index.graph_boost * (1.0 / k)

    # Tier weight, type/kind filter.
    hits: list[RecallHit] = []
    for path, score in scores.items():
        row = rows.get(path)
        if row is None:
            continue
        if type_ is not None and row["type"] != type_:
            continue
        if kind is not None and row["kind"] != kind:
            continue
        tier = Tier(row["tier"])
        hits.append(RecallHit(
            path=path, title=row["title"] or path, tier=tier,
            score=score * _TIER_WEIGHTS.get(tier, 1.0),
            snippet=_snippet(db.body_of(conn, path), terms),
        ))

    hits.sort(key=lambda h: (-h.score, h.path))

    selected: list[RecallHit] = []
    used = 0
    cpt = config.budgets.chars_per_token
    for hit in hits[:limit]:
        cost = estimate_tokens(hit.snippet, cpt)
        if selected and used + cost > max_tokens:
            break
        selected.append(hit)
        used += cost

    db.bump_access(conn, [h.path for h in selected])
    return RecallResult(query=query, hits=selected, total_tokens=used)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_search.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/search.py tests/test_search.py
git commit -m "feat: hybrid retriever (vector + FTS via RRF, tier/recency/graph, filters)"
```

---

### Task 6: Wire the index into `operations.recall` (with keyword fallback)

**Files:**
- Modify: `src/torsor_helper/operations.py`
- Create: `tests/test_recall_via_index.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recall_via_index.py
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


def test_recall_uses_index_and_finds_memory(tmp_path):
    store = _store(tmp_path)
    ops.remember(store, "We adopted RRF for hybrid fusion", kind="decision", links=[])
    res = ops.recall(store, TorsorConfig(), "RRF fusion")
    assert any("RRF" in h.snippet for h in res.hits)
    # the index db was created on disk
    assert store.paths.index_db.exists()


def test_recall_falls_back_to_keyword_when_index_disabled(tmp_path):
    store = _store(tmp_path)
    ops.remember(store, "fallback keyword path works", kind="observation", links=[])
    cfg = TorsorConfig()
    cfg.index.auto_index = False  # no auto-build; no db yet -> keyword fallback
    res = ops.recall(store, cfg, "fallback keyword")
    assert any("fallback" in h.snippet for h in res.hits)
    assert not store.paths.index_db.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_recall_via_index.py -v`
Expected: FAIL — `AssertionError` (index not built / `index_db` missing), since `recall` still uses keyword-only.

- [ ] **Step 3: Implement — replace the `recall` function and add index helpers in `operations.py`**

Add these imports at the top of `operations.py` (keep existing imports):
```python
from torsor_helper import db
from torsor_helper.embeddings import get_embedder
from torsor_helper.indexer import reindex
from torsor_helper.search import hybrid_search
```

Add a module-level embedder cache and an index-opener, then replace the existing `recall`:
```python
_EMBEDDER_CACHE: dict = {}


def _embedder_for(config):
    key = (config.embeddings.provider, config.embeddings.model, config.embeddings.dim)
    if key not in _EMBEDDER_CACHE:
        _EMBEDDER_CACHE[key] = get_embedder(config)
    return _EMBEDDER_CACHE[key]


def _open_index(store, config):
    """Return a freshly-synced index connection, or None to use keyword fallback."""
    if not config.index.auto_index and not store.paths.index_db.exists():
        return None
    embedder = _embedder_for(config)
    conn = db.connect(store.paths.index_db)
    reindex(store, conn, embedder)
    return conn


def recall(store: Store, config: TorsorConfig, query: str, limit: int = 8) -> RecallResult:
    conn = _open_index(store, config)
    if conn is not None:
        try:
            return hybrid_search(
                conn, _embedder_for(config), config, query,
                limit=limit, max_tokens=config.budgets.recall_tokens,
            )
        finally:
            conn.close()
    # Fallback: Phase-1 keyword recall over the Markdown.
    notes = list(store.iter_notes())
    return keyword_recall(
        notes, query, limit=limit,
        chars_per_token=config.budgets.chars_per_token,
        max_tokens=config.budgets.recall_tokens,
    )
```

(Keep the existing `from torsor_helper.recall import keyword_recall` import.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_recall_via_index.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `uv run --extra dev pytest -q`
Expected: PASS. NOTE: `tests/test_operations.py::test_remember_appends_journal_and_recall_finds_it` now exercises the index path — it should still pass (the journal note is indexed and found). If it fails only because the assertion checked a keyword-specific snippet, adjust that one assertion to check `any("SQLite" in h.snippet for h in res.hits)` (same intent).

- [ ] **Step 6: Commit**

```bash
git add src/torsor_helper/operations.py tests/test_recall_via_index.py
git commit -m "feat: recall uses the hybrid index with keyword fallback"
```

---

### Task 7: CLI `torsor index` + doctor index status

**Files:**
- Modify: `src/torsor_helper/cli.py`
- Create: `tests/test_cli_index.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_index.py
from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.paths import TorsorPaths

runner = CliRunner()


def test_index_builds_db_and_reports_counts(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["index", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "indexed" in result.output.lower()
    assert TorsorPaths(tmp_path).index_db.exists()


def test_index_full_rebuild_flag(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    runner.invoke(app, ["index", "--root", str(tmp_path)])
    result = runner.invoke(app, ["index", "--root", str(tmp_path), "--full"])
    assert result.exit_code == 0
    assert "indexed" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_cli_index.py -v`
Expected: FAIL — CLI has no `index` command (exit code 2 / "No such command").

- [ ] **Step 3: Implement — add the `index` command to `cli.py`**

Add imports near the top of `cli.py`:
```python
from torsor_helper import db
from torsor_helper.config import load_config
from torsor_helper.embeddings import get_embedder
from torsor_helper.indexer import reindex
from torsor_helper.store import Store  # if not already imported
```
(`load_config`, `Store`, `TorsorPaths` are already imported in Phase 1 — don't duplicate.)

Add the command:
```python
@app.command()
def index(
    root: Path = typer.Option(Path("."), help="Project root containing .torsor/."),
    full: bool = typer.Option(False, help="Rebuild every note's embedding, ignoring the hash cache."),
) -> None:
    """Build or refresh the derived search index."""
    paths = TorsorPaths(root)
    if not paths.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(paths)
    store = Store(paths)
    conn = db.connect(paths.index_db)
    try:
        stats = reindex(store, conn, get_embedder(config), full=full)
    finally:
        conn.close()
    typer.echo(f"Indexed {stats['indexed']} note(s), deleted {stats['deleted']}, total {stats['total']}.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_cli_index.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/torsor_helper/cli.py tests/test_cli_index.py
git commit -m "feat: torsor index CLI command"
```

---

### Task 8: Coach hooks — `memory/insights/` tier + `recommend` tool stub

**Files:**
- Modify: `src/torsor_helper/paths.py`
- Modify: `src/torsor_helper/store.py`
- Modify: `src/torsor_helper/server.py`
- Create: `tests/test_coach_hooks.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_coach_hooks.py
import anyio

from torsor_helper.paths import TorsorPaths
from torsor_helper.server import build_server
from torsor_helper.store import Store


def test_scaffold_creates_insights_dir(tmp_path):
    paths = TorsorPaths(tmp_path)
    Store(paths).scaffold()
    assert paths.insights_dir.is_dir()
    assert paths.insights_dir == paths.memory_dir / "insights"


def test_server_registers_recommend_stub(tmp_path):
    server = build_server(tmp_path)
    tools = anyio.run(server.list_tools)
    assert "recommend" in {t.name for t in tools}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_coach_hooks.py -v`
Expected: FAIL — `AttributeError: 'TorsorPaths' object has no attribute 'insights_dir'`

- [ ] **Step 3: Implement**

In `paths.py`, add (next to `journal_dir`):
```python
    @property
    def insights_dir(self) -> Path:
        return self.memory_dir / "insights"
```

In `store.py` `scaffold`, add `self.paths.insights_dir` to the tuple of directories created:
```python
        for directory in (
            self.paths.architecture_dir,
            self.paths.decisions_dir,
            self.paths.map_dir,
            self.paths.active_dir,
            self.paths.journal_dir,
            self.paths.insights_dir,
            self.paths.index_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
```

In `server.py`, register the stub tool inside `build_server` (alongside the others):
```python
    @mcp.tool()
    def recommend(context: str = "", limit: int = 5) -> str:
        """Health + best-practice recommendations (the Coach). Arrives in Phase 6."""
        return (
            "The Coach (recommendations) lands in Phase 6. Today, use `bootstrap_session` "
            "for context and `recall` to find prior decisions/learnings."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_coach_hooks.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full suite**

Run: `uv run --extra dev pytest -q`
Expected: PASS (all green). NOTE: `tests/test_server.py` asserts a *subset* of tool names, so adding `recommend` does not break it.

- [ ] **Step 6: Commit**

```bash
git add src/torsor_helper/paths.py src/torsor_helper/store.py src/torsor_helper/server.py tests/test_coach_hooks.py
git commit -m "feat: Coach hooks — insights tier + recommend stub tool"
```

---

### Task 9: Manual smoke test + README/roadmap sync + plan self-review

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Install the embeddings extra and smoke-test real semantic recall**

```bash
uv run --extra dev --extra embeddings python - <<'PY'
import tempfile, datetime
from pathlib import Path
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store
from torsor_helper.config import TorsorConfig
from torsor_helper import operations as ops
d = Path(tempfile.mkdtemp())
store = Store(TorsorPaths(d), clock=lambda: datetime.datetime(2026,6,1,9,30,0))
store.scaffold()
ops.remember(store, "We picked SQLite + RRF for hybrid retrieval", kind="decision", links=[])
print([h.title for h in ops.recall(store, TorsorConfig(), "vector database choice").hits])
PY
```
Expected: prints a non-empty list including the journal note (semantic match via FastEmbed if installed; HashingEmbedder otherwise). No traceback.

- [ ] **Step 2: Smoke-test the CLI index path**

```bash
cd /tmp && rm -rf th-idx && mkdir th-idx && cd th-idx
uv run --project /Users/magnetoid/Documents/trae_projects/torsor-mem torsor init
uv run --project /Users/magnetoid/Documents/trae_projects/torsor-mem torsor index
ls -la .torsor/.index/   # torsor.db present
```
Expected: `index` prints counts; `.torsor/.index/torsor.db` exists. Clean up `/tmp/th-idx` after.

- [ ] **Step 3: Tick the Phase 2 box + update tech stack in README**

In `README.md` Roadmap, change the Phase 2 line to:
```markdown
- [x] **Phase 2 — Index** · SQLite (FTS5 + wiki-link graph) + local embeddings (NumPy cosine), incremental indexer, hybrid RRF recall *(shipped)*
```
And update the `recall` tool row Status to `✅ **shipped**` with note "(hybrid semantic)", and the "Built with" line to list `numpy` (today) and `fastembed` (optional extra).

- [ ] **Step 4: Run the full suite a final time**

Run: `uv run --extra dev pytest -q`
Expected: PASS (all green).

- [ ] **Step 5: Commit and push**

```bash
git add README.md
git commit -m "docs: mark Phase 2 (index) complete"
git push
```

---

## Self-Review

**Spec coverage** (Phase-2 scope from the design spec §13 + Coach hooks §8):
- SQLite index (FTS5 + edges + meta) → Task 3
- Local embeddings, no API key, optional fastembed → Task 2
- Vector search (NumPy cosine over BLOBs; `sqlite-vec` deliberately deferred) → Tasks 2–3 (documented refinement)
- Incremental indexer (content-hash diff, delete removed) → Task 4
- Hybrid retrieval (vector + FTS via RRF + tier + recency + 1-hop graph + budget) → Task 5
- Wiki-link graph → Tasks 3–4 (edges) + Task 5 (boost)
- `recall` uses index with graceful keyword fallback → Task 6
- CLI `torsor index` → Task 7
- **Coach hooks:** `type`/`kind` stored + filterable (Tasks 3, 5), `access_count` tracked (Tasks 3, 5), `memory/insights/` scaffolded (Task 8), thin `recommend` stub (Task 8)
- **Deferred (later phases):** tree-sitter map + `get_intent`/`map_repo` (Phase 3); ADR rules + `check_drift` (Phase 4); `consolidate`/insight mining (Phases 5–6); live file-watcher (`watchfiles`) — recall auto-reindexes incrementally instead, which is sufficient for Phase 2.

**Placeholder scan:** none — every code/test step has runnable content.

**Type consistency:** names match the locked contracts across tasks — `get_embedder`, `db.connect`/`pack`/`unpack`/`cosine_search`/`fts_search`/`note_row`/`body_of`/`neighbors`/`bump_access`/`upsert_note`/`replace_fts`/`replace_edges`/`upsert_vector`/`delete_note`/`note_hashes`, `reindex(...)->stats`, `hybrid_search(...)->RecallResult`, `IndexConfig`/`EmbeddingConfig.dim`, `insights_dir`. `RecallResult`/`RecallHit`/`Tier` reused unchanged from Phase 1.

## Notes for the implementer
- All tests use `HashingEmbedder` — never download a model in the suite. The `embeddings` extra is only exercised in the Task 9 manual smoke.
- `operations.recall` now auto-reindexes (incremental, cheap) before searching; keep that behavior — it's what keeps the index correct without a file-watcher.
- Keep `db.py` free of business logic (pure storage/query helpers); keep `server.py`/`cli.py` thin.
