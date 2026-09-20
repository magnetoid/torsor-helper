"""Opening the index, and re-running the map, must not do work that changed nothing.

Both are on hot paths: every CLI command and every recall opens a connection,
and the post-commit hook re-maps on every commit.
"""
from __future__ import annotations

import sqlite3

from torsor_helper import db, operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def test_opening_a_current_index_does_not_rebuild_the_schema(tmp_path):
    path = tmp_path / "i.db"
    db.connect(path).close()          # create it once

    issued: list[str] = []
    orig = sqlite3.connect

    def traced(*a, **k):
        c = orig(*a, **k)
        c.set_trace_callback(issued.append)
        return c

    sqlite3.connect = traced
    try:
        db.connect(path).close()
    finally:
        sqlite3.connect = orig

    sql = " ".join(issued).upper()
    assert "CREATE TABLE" not in sql
    assert "CREATE INDEX" not in sql
    assert "INSERT INTO META" not in sql


def test_a_fresh_index_is_still_created(tmp_path):
    conn = db.connect(tmp_path / "i.db")
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"notes", "vectors", "edges", "symbols", "symbol_edges"} <= tables
        assert int(db.meta_get(conn, "schema_version")) == db.SCHEMA_VERSION
    finally:
        conn.close()


def test_an_older_index_is_still_migrated(tmp_path):
    path = tmp_path / "i.db"
    conn = db.connect(path)
    db.meta_set(conn, "schema_version", "6")   # pretend it was built by an older torsor
    conn.execute("DROP INDEX IF EXISTS idx_edges_src")
    conn.commit()
    conn.close()

    conn = db.connect(path)
    try:
        idx = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert "idx_edges_src" in idx
        assert int(db.meta_get(conn, "schema_version")) == db.SCHEMA_VERSION
    finally:
        conn.close()


def test_remapping_an_unchanged_repo_rewrites_no_map_notes(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "a.py").write_text("def f():\n    return 1\n")
    (tmp_path / "b.py").write_text("def g():\n    return 2\n")
    config = TorsorConfig()
    ops.map_repo(store, config)

    before = {p: p.stat().st_mtime_ns for p in store.paths.map_dir.rglob("*.md")}
    assert before

    ops.map_repo(store, config, force=True)   # force: skip the fingerprint shortcut

    after = {p: p.stat().st_mtime_ns for p in store.paths.map_dir.rglob("*.md")}
    assert after == before, "identical map notes were rewritten, churning git and the index"


def test_remapping_after_a_real_change_does_rewrite(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "a.py").write_text("def f():\n    return 1\n")
    config = TorsorConfig()
    ops.map_repo(store, config)
    note = next(p for p in store.paths.map_dir.rglob("*a.py.md"))
    before = note.read_text(encoding="utf-8")

    (tmp_path / "a.py").write_text("def f():\n    return 1\n\n\ndef added():\n    return 2\n")
    ops.map_repo(store, config, force=True)

    assert "added" in note.read_text(encoding="utf-8")
    assert note.read_text(encoding="utf-8") != before
