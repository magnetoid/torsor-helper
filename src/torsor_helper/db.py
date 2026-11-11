from __future__ import annotations

import math
import re
import sqlite3
from array import array
from operator import mul
from pathlib import Path
from typing import Callable, Iterable, Sequence

from torsor_helper.models import Symbol, SymbolEdge

# Vectors are float32 arrays packed with `array('f')`; numpy is not a dependency.
# It was the single most expensive import in the process for four functions, so
# the required path is plain Python, and cosine_search picks numpy up only when
# something else (the `[embeddings]` extra, whose fastembed needs it) installed
# it. tests/test_no_numpy.py runs both paths; tests/test_import_budget.py pins
# that the hook and --help never load it.


def _sum_of_products(a: Iterable[float], b: Iterable[float]) -> float:
    return sum(map(mul, a, b))


# 3.12+ has the same product-sum in C, ~40 % faster; getattr keeps mypy on 3.11
# (where the attribute does not exist) from flagging a dead branch.
_dot: Callable[[Iterable[float], Iterable[float]], float] = getattr(math, "sumprod", _sum_of_products)


def _numpy():
    """numpy if installed, else None. A function so tests can force the pure path."""
    try:
        import numpy as np
    except ImportError:
        return None
    return np

SCHEMA_VERSION = 9


def connect(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    # Recall is a writer (reindex + access bumps), and the MCP server and CLI
    # can run concurrently — WAL + a generous busy timeout prevent
    # "database is locked" failures under that contention.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    # WAL already gives durability across process crashes; FULL additionally
    # fsyncs on every commit, which recall pays on its access bumps.
    conn.execute("PRAGMA synchronous=NORMAL")
    if _schema_is_current(conn):
        return conn
    _create_schema(conn)
    return conn


def _schema_is_current(conn: sqlite3.Connection) -> bool:
    """True when this DB was already built by this version.

    Every CLI command and every recall opens a connection, and _create_schema is
    a write transaction — ten CREATEs, two PRAGMA table_info, a meta write and a
    commit — so running it unconditionally meant a write (and an fsync) before
    any read. A missing meta table, an older stamp or any error all fall through
    to the full path, which is idempotent.

    The trade-off: the stamp is now trusted, so **a change to the schema must
    come with a SCHEMA_VERSION bump**. An unbumped change used to be absorbed
    silently by the unconditional rebuild; now it would never reach an index
    that already exists."""
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    except sqlite3.Error:
        return False
    try:
        return row is not None and int(row["value"]) == SCHEMA_VERSION
    except (TypeError, ValueError):
        return False


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS notes (
            path TEXT PRIMARY KEY, content_hash TEXT, tier INTEGER,
            type TEXT, kind TEXT, title TEXT, updated TEXT,
            access_count INTEGER NOT NULL DEFAULT 0, status TEXT,
            mtime_ns INTEGER, size INTEGER
        );
        CREATE TABLE IF NOT EXISTS vectors (path TEXT PRIMARY KEY, dim INTEGER, embedding BLOB);
        CREATE TABLE IF NOT EXISTS edges (src TEXT, target_slug TEXT, target_path TEXT);
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        -- note -> symbol name, the other direction from `edges` (note -> note).
        -- Unfiltered: whether a mention names a real symbol is decided by
        -- joining `symbols` at query time, so the two indexes can be built
        -- in either order. See store.extract_symbol_mentions.
        CREATE TABLE IF NOT EXISTS note_symbols (path TEXT, symbol TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(path UNINDEXED, title, body);
        CREATE TABLE IF NOT EXISTS symbols (
            name TEXT, kind TEXT, signature TEXT, module TEXT,
            line INTEGER, doc TEXT, refs INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS symbol_edges (
            caller TEXT, referenced_name TEXT, role TEXT,
            module TEXT, resolved_module TEXT, hint TEXT
        );
        CREATE TABLE IF NOT EXISTS path_access (
            path TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0, last_seen INTEGER NOT NULL DEFAULT 0
        );

        -- Secondary indexes. Every one of these backed a query that was a full
        -- table scan: who_references ran one per candidate module inside impact,
        -- neighbors runs on the recall hot path, and db.modules feeds the
        -- cleaner.
        CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
        CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_path);
        CREATE INDEX IF NOT EXISTS idx_symbols_module ON symbols(module);
        CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
        CREATE INDEX IF NOT EXISTS idx_symbol_edges_resolved
            ON symbol_edges(resolved_module, referenced_name);
        CREATE INDEX IF NOT EXISTS idx_symbol_edges_module ON symbol_edges(module);
        CREATE INDEX IF NOT EXISTS idx_notes_type ON notes(type, kind);
        CREATE INDEX IF NOT EXISTS idx_note_symbols_symbol ON note_symbols(symbol);
        CREATE INDEX IF NOT EXISTS idx_note_symbols_path ON note_symbols(path);

        -- path -> the FTS row holding that note's body. `fts.path` is UNINDEXED
        -- (searching it would pollute the match), so every lookup by path was a
        -- full scan of the FTS table — and search does one per result it shows.
        CREATE TABLE IF NOT EXISTS fts_map (path TEXT PRIMARY KEY, rowid_ INTEGER NOT NULL);
        """
    )
    # Additive column migration for DBs created before `status` existed
    # (ADD COLUMN is idempotent-guarded; a fresh DB already has it via CREATE).
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(notes)")}
    for col, decl in (("status", "TEXT"), ("mtime_ns", "INTEGER"), ("size", "INTEGER")):
        if col not in cols:
            conn.execute(f"ALTER TABLE notes ADD COLUMN {col} {decl}")
    # Same additive migration for `symbol_edges.hint` (schema 7): the Go
    # resolver branches on it, so an edge that loses its hint on the round-trip
    # is silently mis-resolved on the next partial map.
    edge_cols = {r["name"] for r in conn.execute("PRAGMA table_info(symbol_edges)")}
    if "hint" not in edge_cols:
        conn.execute("ALTER TABLE symbol_edges ADD COLUMN hint TEXT")
    # Always stamp the current version: tables are created additively via
    # CREATE TABLE IF NOT EXISTS, so an upgraded DB must report the live version.
    meta_set(conn, "schema_version", str(SCHEMA_VERSION))
    conn.commit()


def meta_get(conn, key):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def meta_set(conn, key, value):
    conn.execute(
        "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=?",
        (key, value, value),
    )


def pack(vec: Sequence[float]) -> bytes:
    """Store L2-normalized, so cosine similarity at query time is a plain dot
    product and the whole table can be multiplied at once. A zero vector stays
    zero and scores 0 against everything, which is what it meant before."""
    arr = array("f", vec)
    norm = math.sqrt(sum(x * x for x in arr))
    if norm > 0.0:
        arr = array("f", (x / norm for x in arr))
    return arr.tobytes()


def unpack(blob: bytes) -> array[float]:
    arr = array("f")
    arr.frombytes(blob)
    return arr


def note_hashes(conn) -> dict[str, str]:
    return {r["path"]: r["content_hash"] for r in conn.execute("SELECT path, content_hash FROM notes")}


def note_stats(conn) -> dict[str, dict]:
    """{path: {content_hash, mtime_ns, size}} — the indexer's skip-screen inputs."""
    return {
        r["path"]: {"content_hash": r["content_hash"], "mtime_ns": r["mtime_ns"], "size": r["size"]}
        for r in conn.execute("SELECT path, content_hash, mtime_ns, size FROM notes")
    }


def note_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]


def update_note_stat(conn, path, mtime_ns, size):
    conn.execute("UPDATE notes SET mtime_ns=?, size=? WHERE path=?", (mtime_ns, size, path))


def upsert_note(conn, path, content_hash, tier, type_, kind, title, updated, status="active",
                mtime_ns=None, size=None):
    conn.execute(
        """INSERT INTO notes(path, content_hash, tier, type, kind, title, updated, status, mtime_ns, size)
           VALUES(?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(path) DO UPDATE SET
             content_hash=excluded.content_hash, tier=excluded.tier, type=excluded.type,
             kind=excluded.kind, title=excluded.title, updated=excluded.updated, status=excluded.status,
             mtime_ns=excluded.mtime_ns, size=excluded.size""",
        (path, content_hash, int(tier), type_, kind, title, updated, status, mtime_ns, size),
    )


def note_row(conn, path):
    row = conn.execute("SELECT * FROM notes WHERE path=?", (path,)).fetchone()
    return dict(row) if row else None


def note_rows(conn, paths) -> dict[str, dict]:
    """{path: row} for many paths in one statement. The per-path note_row was an
    N+1: search called it once per candidate, and a type/kind filter widens the
    candidate set to the whole corpus."""
    paths = list(paths)
    out: dict[str, dict] = {}
    for i in range(0, len(paths), 400):  # stay under SQLite's variable limit
        chunk = paths[i:i + 400]
        marks = ",".join("?" * len(chunk))
        for row in conn.execute(f"SELECT * FROM notes WHERE path IN ({marks})", chunk):
            out[row["path"]] = dict(row)
    return out


def _fts_rowid(conn, path) -> int | None:
    row = conn.execute("SELECT rowid_ FROM fts_map WHERE path=?", (path,)).fetchone()
    return row["rowid_"] if row else None


def replace_fts(conn, path, title, body):
    old = _fts_rowid(conn, path)
    if old is not None:
        conn.execute("DELETE FROM fts WHERE rowid=?", (old,))
    cur = conn.execute("INSERT INTO fts(path, title, body) VALUES(?,?,?)", (path, title, body))
    conn.execute(
        "INSERT INTO fts_map(path, rowid_) VALUES(?,?) "
        "ON CONFLICT(path) DO UPDATE SET rowid_=excluded.rowid_",
        (path, cur.lastrowid),
    )


def body_of(conn, path):
    rowid = _fts_rowid(conn, path)
    if rowid is None:
        return ""
    row = conn.execute("SELECT body FROM fts WHERE rowid=?", (rowid,)).fetchone()
    return row["body"] if row else ""


def _note_paths(conn) -> list[str]:
    return [r["path"] for r in conn.execute("SELECT path FROM notes ORDER BY path")]


class SlugIndex:
    """slug -> the first (sorted) note path ending in `<slug>.md`.

    Exactly what scanning the path list per slug answered, computed once. The
    scan was O(notes) per distinct slug and ran over every edge on every
    reindex — 2.3s of an 11.8s recall over 5k notes.

    A slug containing "/" (`[[dir/note]]`) still needs the scan, because it
    matches on a path *suffix* rather than a basename. Those are rare, so they
    keep the old path rather than changing what resolves to what."""

    def __init__(self, conn) -> None:
        self.paths = _note_paths(conn)
        self.by_basename: dict[str, str] = {}
        self.ambiguous: set[str] = set()
        for p in self.paths:
            # Tolerate a backslash path from an index built by an older version
            # on Windows; the indexer writes posix now.
            name = p.replace("\\", "/").rsplit("/", 1)[-1]
            if not name.endswith(".md"):
                continue
            slug = name[:-3]
            if slug in self.by_basename:
                # Two tiers can both hold an `overview.md`. The first sorted one
                # keeps winning — changing that would silently re-point existing
                # links — but the collision is now visible to the Coach.
                self.ambiguous.add(slug)
            else:
                self.by_basename[slug] = p

    def is_ambiguous(self, slug: str) -> bool:
        """True when more than one note shares this basename. A slug containing
        "/" is a path tail, which is how a writer disambiguates, so it never is."""
        return "/" not in slug and slug in self.ambiguous

    def resolve(self, slug: str) -> str | None:
        if "/" not in slug:
            return self.by_basename.get(slug)
        suffix = f"/{slug}.md"
        exact = f"{slug}.md"
        for p in self.paths:
            norm = p.replace("\\", "/")
            if norm == exact or norm.endswith(suffix):
                return p
        return None


def _resolve_slug(paths: list[str], slug: str) -> str | None:
    """Literal suffix match, so LIKE wildcards in a slug can't match the wrong
    note. Kept for callers holding a plain path list; SlugIndex is the fast path."""
    exact, suffix = f"{slug}.md", f"/{slug}.md"
    for p in paths:
        if p == exact or p.endswith(suffix):
            return p
    return None


def replace_edges(conn, src, slugs, index: SlugIndex | None = None):
    """`index` lets a bulk caller build the slug lookup once instead of running a
    full SELECT per note being indexed."""
    conn.execute("DELETE FROM edges WHERE src=?", (src,))
    idx = index or SlugIndex(conn)
    for slug in slugs:
        conn.execute(
            "INSERT INTO edges(src, target_slug, target_path) VALUES(?,?,?)",
            (src, slug, idx.resolve(slug)),
        )


def replace_note_symbols(conn, path, symbols) -> None:
    conn.execute("DELETE FROM note_symbols WHERE path=?", (path,))
    conn.executemany(
        "INSERT INTO note_symbols(path, symbol) VALUES(?,?)",
        [(path, s) for s in symbols],
    )


def notes_mentioning(conn, symbol: str) -> list[str]:
    """Note paths that name `symbol` in backticks, newest first.

    No join against `symbols` here: the caller already has a symbol name in
    hand. The join matters the other way round, for "what does this note talk
    about", which nothing needs yet."""
    rows = conn.execute(
        "SELECT ns.path AS path FROM note_symbols ns "
        "LEFT JOIN notes n ON n.path = ns.path "
        "WHERE ns.symbol = ? GROUP BY ns.path ORDER BY n.updated DESC, ns.path",
        (symbol,),
    ).fetchall()
    return [r["path"] for r in rows]


def reresolve_edges(conn) -> None:
    """Second resolution pass over ALL edges: insert-time resolution only sees
    notes already upserted, so links to notes indexed later (or created later)
    would otherwise stay NULL forever — and links to deleted notes stay stale."""
    idx = SlugIndex(conn)
    resolved: dict[str, str | None] = {}
    for row in conn.execute("SELECT rowid, target_slug, target_path FROM edges").fetchall():
        slug = row["target_slug"]
        if slug not in resolved:
            resolved[slug] = idx.resolve(slug)
        if row["target_path"] != resolved[slug]:
            conn.execute("UPDATE edges SET target_path=? WHERE rowid=?", (resolved[slug], row["rowid"]))


def neighbors(conn, path):
    return [
        r["target_path"]
        for r in conn.execute(
            "SELECT target_path FROM edges WHERE src=? AND target_path IS NOT NULL", (path,)
        )
    ]


def upsert_vector(conn, path, vec):
    blob = pack(vec)
    conn.execute(
        "INSERT INTO vectors(path, dim, embedding) VALUES(?,?,?) "
        "ON CONFLICT(path) DO UPDATE SET dim=excluded.dim, embedding=excluded.embedding",
        (path, len(vec), blob),
    )


def delete_note(conn, path):
    conn.execute("DELETE FROM notes WHERE path=?", (path,))
    conn.execute("DELETE FROM vectors WHERE path=?", (path,))
    conn.execute("DELETE FROM edges WHERE src=?", (path,))
    conn.execute("DELETE FROM note_symbols WHERE path=?", (path,))
    rowid = _fts_rowid(conn, path)
    if rowid is not None:
        conn.execute("DELETE FROM fts WHERE rowid=?", (rowid,))
    conn.execute("DELETE FROM fts_map WHERE path=?", (path,))


def get_vectors(conn, paths):
    """Return {path: array('f')} for the given paths that have a stored vector."""
    paths = list(paths)
    out = {}
    for i in range(0, len(paths), 400):  # stay under SQLite's variable limit
        chunk = paths[i:i + 400]
        marks = ",".join("?" * len(chunk))
        for row in conn.execute(
            f"SELECT path, embedding FROM vectors WHERE path IN ({marks})", chunk
        ):
            out[row["path"]] = unpack(row["embedding"])
    return out


def vectors_match(conn, embedder_identity: str) -> bool:
    """True when the stored vectors were built by this run's embedder. A False
    here means the vector leg must be skipped: comparing a hashing query vector
    against fastembed document vectors is noise, not a weaker signal."""
    stored = meta_get(conn, "embedder")
    return stored is None or stored == embedder_identity


def cosine_search(conn, qvec, limit):
    """Top-`limit` paths by cosine similarity to `qvec`.

    The vectors are stored normalized (see pack), and `dim` filters out any left
    over from a different embedder, so each row is one dot product against the
    unit query. With numpy present that is one matrix multiply over the whole
    table; without it, one product-sum per row. Measured on 5 000 notes x 384:
    18 ms with numpy, 53 ms without — a few percent of a warm recall, and the
    price of not shipping numpy."""
    q = array("f", qvec)
    qn = math.sqrt(sum(x * x for x in q))
    if qn == 0.0:
        return []
    rows = conn.execute(
        "SELECT path, embedding FROM vectors WHERE dim=? ORDER BY path", (len(q),)
    ).fetchall()
    if not rows:
        return []
    np = _numpy()
    if np is not None:
        unit = np.asarray(q, dtype=np.float32) / np.float32(qn)
        matrix = np.frombuffer(b"".join(r["embedding"] for r in rows), dtype=np.float32)
        sims = matrix.reshape(len(rows), len(q)) @ unit
        # Rows are path-ordered, so a stable sort on -score breaks ties by path.
        order = np.argsort(-sims, kind="stable")[:limit]
        return [(rows[i]["path"], float(sims[i])) for i in order]
    unit_q = [x / qn for x in q]
    scored = [(r["path"], _dot(unpack(r["embedding"]), unit_q)) for r in rows]
    scored.sort(key=lambda t: -t[1])  # stable: ties stay in path order
    return scored[:limit]


def fts_search(conn, query, limit):
    terms = [t for t in re.findall(r"\w+", query.lower()) if t]
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


def replace_all_symbols(conn, symbols):
    conn.execute("DELETE FROM symbols")
    conn.executemany(
        "INSERT INTO symbols(name, kind, signature, module, line, doc, refs) VALUES(?,?,?,?,?,?,?)",
        [(s.name, s.kind, s.signature, s.module, s.line, s.doc, s.refs) for s in symbols],
    )
    conn.commit()


def replace_all_edges(conn, edges):
    conn.execute("DELETE FROM symbol_edges")
    conn.executemany(
        "INSERT INTO symbol_edges(caller, referenced_name, role, module, resolved_module, hint) "
        "VALUES(?,?,?,?,?,?)",
        [(e.caller, e.referenced_name, e.role, e.module, e.resolved_module, e.hint) for e in edges],
    )
    conn.commit()


def vacuum(conn) -> None:
    """Give freed pages back to the filesystem. SQLite keeps them otherwise, so
    deleting most of a table leaves the file exactly as large as it was."""
    conn.commit()
    conn.execute("VACUUM")


def who_references(conn, resolved_module, name):
    """Return [(caller, module)] of references to `name` resolving to `resolved_module`."""
    rows = conn.execute(
        "SELECT DISTINCT caller, module FROM symbol_edges "
        "WHERE resolved_module=? AND referenced_name=? ORDER BY module, caller",
        (resolved_module, name),
    ).fetchall()
    return [(r["caller"], r["module"]) for r in rows]


def call_graph_edges(conn):
    """Distinct (caller, referenced_name, resolved_module) directed edges of the
    symbol call graph. Used by `connect` to walk who-calls-what paths. Edges with
    an unresolved target are dropped — a path hop must land in a known module."""
    rows = conn.execute(
        "SELECT DISTINCT caller, referenced_name, resolved_module FROM symbol_edges "
        "WHERE resolved_module IS NOT NULL AND role='call'"
    ).fetchall()
    return [(r["caller"], r["referenced_name"], r["resolved_module"]) for r in rows]


def symbol_fan_in(conn):
    """In-degree of each referenced symbol: (resolved_module, referenced_name,
    fan_in) where fan_in is the count of *distinct* calling symbols. Powers the
    coach's 'God node' (hub) detection — symbols many others depend on."""
    rows = conn.execute(
        "SELECT resolved_module, referenced_name, "
        "COUNT(DISTINCT caller || '@' || module) AS fan_in FROM symbol_edges "
        "WHERE resolved_module IS NOT NULL AND role='call' "
        "GROUP BY resolved_module, referenced_name"
    ).fetchall()
    return [(r["resolved_module"], r["referenced_name"], r["fan_in"]) for r in rows]


def module_edges(conn):
    """Distinct (module, resolved_module) pairs for module-level dependency views."""
    rows = conn.execute(
        "SELECT DISTINCT module, resolved_module FROM symbol_edges "
        "WHERE resolved_module IS NOT NULL ORDER BY module, resolved_module"
    ).fetchall()
    return [(r["module"], r["resolved_module"]) for r in rows]


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


def all_symbols(conn):
    """Lightweight dicts for every mapped symbol."""
    rows = conn.execute("SELECT name, kind, signature, module, line, refs FROM symbols").fetchall()
    return [dict(r) for r in rows]


def load_symbols(conn) -> list[Symbol]:
    """Full Symbol objects for every mapped symbol — used when merging a partial
    map into the existing graph (unlike all_symbols, carries doc)."""
    rows = conn.execute("SELECT name, kind, signature, module, line, doc, refs FROM symbols").fetchall()
    return [
        Symbol(name=r["name"], kind=r["kind"], signature=r["signature"],
               module=r["module"], line=r["line"], doc=r["doc"] or "", refs=r["refs"])
        for r in rows
    ]


def load_edges(conn) -> list[SymbolEdge]:
    """Full SymbolEdge objects for every recorded reference edge."""
    rows = conn.execute(
        "SELECT caller, referenced_name, role, module, resolved_module, hint FROM symbol_edges"
    ).fetchall()
    return [
        SymbolEdge(caller=r["caller"], referenced_name=r["referenced_name"], role=r["role"],
                   module=r["module"], resolved_module=r["resolved_module"], hint=r["hint"])
        for r in rows
    ]


def find_clock(conn) -> int:
    return int(meta_get(conn, "find_clock") or 0)


def bump_path_access(conn, paths):
    """Record that these files were surfaced by a find — frecency signal. The
    recency stamp is a monotonic per-find counter (deterministic, no clock)."""
    if not paths:
        return
    clock = find_clock(conn) + 1
    meta_set(conn, "find_clock", str(clock))
    for p in paths:
        conn.execute(
            "INSERT INTO path_access(path, count, last_seen) VALUES(?,1,?) "
            "ON CONFLICT(path) DO UPDATE SET count=count+1, last_seen=?",
            (p, clock, clock),
        )
    conn.commit()


def path_access_map(conn) -> dict:
    return {r["path"]: (r["count"], r["last_seen"]) for r in conn.execute("SELECT path, count, last_seen FROM path_access")}


def top_accessed(conn, limit=5):
    rows = conn.execute(
        "SELECT path, access_count FROM notes WHERE access_count > 0 "
        "ORDER BY access_count DESC, path LIMIT ?",
        (limit,),
    ).fetchall()
    return [(r["path"], r["access_count"]) for r in rows]
