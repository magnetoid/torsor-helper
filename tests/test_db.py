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
    db.upsert_note(conn, "a.md", "h2", 4, "journal", None, "A", "2026-06-01T10:00:00")
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
    assert ranked[1][0] == "z.md"


def test_edges_and_neighbors(tmp_path):
    conn = _conn(tmp_path)
    db.upsert_note(conn, "charter.md", "h", 0, "charter", None, "Charter", "t")
    db.replace_edges(conn, "note.md", ["charter"])
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
