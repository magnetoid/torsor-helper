from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Sequence

import numpy as np

from torsor_helper.models import Symbol, SymbolEdge

SCHEMA_VERSION = 6


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
    _create_schema(conn)
    return conn


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
        CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(path UNINDEXED, title, body);
        CREATE TABLE IF NOT EXISTS symbols (
            name TEXT, kind TEXT, signature TEXT, module TEXT,
            line INTEGER, doc TEXT, refs INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS symbol_edges (
            caller TEXT, referenced_name TEXT, role TEXT,
            module TEXT, resolved_module TEXT
        );
        CREATE TABLE IF NOT EXISTS complexity_snapshot (
            file TEXT PRIMARY KEY, complexity INTEGER
        );
        CREATE TABLE IF NOT EXISTS path_access (
            path TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0, last_seen INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS op_log (
            op TEXT, args TEXT, hits INTEGER NOT NULL DEFAULT 0, last_used INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(op, args)
        );
        """
    )
    # Additive column migration for DBs created before `status` existed
    # (ADD COLUMN is idempotent-guarded; a fresh DB already has it via CREATE).
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(notes)")}
    for col, decl in (("status", "TEXT"), ("mtime_ns", "INTEGER"), ("size", "INTEGER")):
        if col not in cols:
            conn.execute(f"ALTER TABLE notes ADD COLUMN {col} {decl}")
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
    return np.asarray(list(vec), dtype=np.float32).tobytes()


def unpack(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


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


def replace_fts(conn, path, title, body):
    conn.execute("DELETE FROM fts WHERE path=?", (path,))
    conn.execute("INSERT INTO fts(path, title, body) VALUES(?,?,?)", (path, title, body))


def body_of(conn, path):
    row = conn.execute("SELECT body FROM fts WHERE path=?", (path,)).fetchone()
    return row["body"] if row else ""


def _note_paths(conn) -> list[str]:
    return [r["path"] for r in conn.execute("SELECT path FROM notes ORDER BY path")]


def _resolve_slug(paths: list[str], slug: str) -> str | None:
    """First (sorted) note whose path ends in `<slug>.md` — literal matching, so
    LIKE wildcards in slugs ('_', '%') can't match the wrong note."""
    exact, suffix = f"{slug}.md", f"/{slug}.md"
    for p in paths:
        if p == exact or p.endswith(suffix):
            return p
    return None


def replace_edges(conn, src, slugs):
    conn.execute("DELETE FROM edges WHERE src=?", (src,))
    paths = _note_paths(conn)
    for slug in slugs:
        conn.execute(
            "INSERT INTO edges(src, target_slug, target_path) VALUES(?,?,?)",
            (src, slug, _resolve_slug(paths, slug)),
        )


def reresolve_edges(conn) -> None:
    """Second resolution pass over ALL edges: insert-time resolution only sees
    notes already upserted, so links to notes indexed later (or created later)
    would otherwise stay NULL forever — and links to deleted notes stay stale."""
    paths = _note_paths(conn)
    resolved: dict[str, str | None] = {}
    for row in conn.execute("SELECT rowid, target_slug, target_path FROM edges").fetchall():
        slug = row["target_slug"]
        if slug not in resolved:
            resolved[slug] = _resolve_slug(paths, slug)
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
    conn.execute("DELETE FROM fts WHERE path=?", (path,))


def get_vectors(conn, paths):
    """Return {path: np.ndarray} for the given paths that have a stored vector."""
    out = {}
    for p in paths:
        row = conn.execute("SELECT embedding FROM vectors WHERE path=?", (p,)).fetchone()
        if row is not None:
            out[p] = unpack(row["embedding"])
    return out


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
        if v.shape[0] != q.shape[0]:
            continue  # stale-dimension vector (embedder changed) — skip defensively
        vn = np.linalg.norm(v)
        if vn == 0:
            continue
        scored.append((r["path"], float(np.dot(q, v / vn))))
    scored.sort(key=lambda t: (-t[1], t[0]))
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
        "INSERT INTO symbol_edges(caller, referenced_name, role, module, resolved_module) VALUES(?,?,?,?,?)",
        [(e.caller, e.referenced_name, e.role, e.module, e.resolved_module) for e in edges],
    )
    conn.commit()


def who_references(conn, resolved_module, name):
    """Return [(caller, module)] of references to `name` resolving to `resolved_module`."""
    rows = conn.execute(
        "SELECT DISTINCT caller, module FROM symbol_edges "
        "WHERE resolved_module=? AND referenced_name=? ORDER BY module, caller",
        (resolved_module, name),
    ).fetchall()
    return [(r["caller"], r["module"]) for r in rows]


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
    """Lightweight dicts for every mapped symbol — for fuzzy-scoring by the finder."""
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
        "SELECT caller, referenced_name, role, module, resolved_module FROM symbol_edges"
    ).fetchall()
    return [
        SymbolEdge(caller=r["caller"], referenced_name=r["referenced_name"], role=r["role"],
                   module=r["module"], resolved_module=r["resolved_module"])
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


def log_op(conn, op, args):
    """Record one deterministic-tool call — the frequency signal behind 'recipes'
    (what the agent does repeatedly). Recency is a monotonic counter, not a clock."""
    clock = int(meta_get(conn, "op_clock") or 0) + 1
    meta_set(conn, "op_clock", str(clock))
    conn.execute(
        "INSERT INTO op_log(op, args, hits, last_used) VALUES(?,?,1,?) "
        "ON CONFLICT(op, args) DO UPDATE SET hits=hits+1, last_used=?",
        (op, args, clock, clock),
    )
    conn.commit()


def top_ops(conn, limit=10):
    rows = conn.execute(
        "SELECT op, args, hits FROM op_log ORDER BY hits DESC, last_used DESC, op LIMIT ?",
        (limit,),
    ).fetchall()
    return [{"op": r["op"], "args": r["args"], "hits": r["hits"]} for r in rows]


def op_totals(conn) -> dict[str, int]:
    """Total hits per op, aggregated across args — the per-session delta baseline
    for the deterministic auto-handoff digest."""
    rows = conn.execute("SELECT op, SUM(hits) AS n FROM op_log GROUP BY op").fetchall()
    return {r["op"]: int(r["n"]) for r in rows}


def save_complexity_snapshot(conn, mapping):
    """Replace the stored per-file complexity baseline (for trend detection)."""
    conn.execute("DELETE FROM complexity_snapshot")
    conn.executemany(
        "INSERT INTO complexity_snapshot(file, complexity) VALUES(?,?)",
        [(f, int(c)) for f, c in mapping.items()],
    )
    conn.commit()


def load_complexity_snapshot(conn) -> dict:
    return {r["file"]: r["complexity"] for r in conn.execute("SELECT file, complexity FROM complexity_snapshot")}


def top_accessed(conn, limit=5):
    rows = conn.execute(
        "SELECT path, access_count FROM notes WHERE access_count > 0 "
        "ORDER BY access_count DESC, path LIMIT ?",
        (limit,),
    ).fetchall()
    return [(r["path"], r["access_count"]) for r in rows]
