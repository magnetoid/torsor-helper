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
    assert stats["indexed"] >= 6
    assert stats["total"] == stats["indexed"]
    assert db.cosine_search(conn, HashingEmbedder(64).embed(["architecture"])[0], 50)


def test_reindex_rebuilds_when_embedder_dim_changes(tmp_path):
    store, conn = _setup(tmp_path)
    reindex(store, conn, HashingEmbedder(dim=64))
    # Switching to a different-dim embedder must force a full re-embed (no crash,
    # no mixed dimensions) — reachable when config.embeddings.dim changes between runs.
    stats = reindex(store, conn, HashingEmbedder(dim=128))
    assert stats["indexed"] == stats["total"]  # everything re-embedded
    # cosine search with a 128-dim query must work and not raise on stale 64-dim rows
    hits = db.cosine_search(conn, HashingEmbedder(dim=128).embed(["architecture"])[0], 50)
    assert hits
    assert db.meta_get(conn, "embedder") == "hashing::128"


def test_reindex_is_incremental(tmp_path):
    store, conn = _setup(tmp_path)
    reindex(store, conn, HashingEmbedder(dim=64))
    stats = reindex(store, conn, HashingEmbedder(dim=64))
    assert stats["indexed"] == 0
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
    store.append_journal("learned X", kind="learning", links=["charter"])
    reindex(store, conn, HashingEmbedder(dim=64))
    journal = store.paths.journal_file("2026-06-01")
    row = db.note_row(conn, str(journal))
    assert row["type"] == "journal"
    assert db.neighbors(conn, str(journal)) == [str(store.paths.charter)]


def test_reindex_survives_malformed_and_undecodable_notes(tmp_path):
    import warnings

    store, conn = _setup(tmp_path)
    bad_dir = store.paths.journal_dir
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "bad-yaml.md").write_text("---\nfoo: [unclosed\n---\n\nstill text\n")
    (bad_dir / "bad-date.md").write_text("---\ntype: note\ncreated: 2026-06-01\n---\n\n# D\n\nbody\n")
    (bad_dir / "bad-bytes.md").write_bytes(b"\xff\xfe not utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        stats = reindex(store, conn, HashingEmbedder(dim=64))
    assert stats["indexed"] >= 8  # one bad note must not brick the whole index


def test_reindex_full_when_index_schema_changes(tmp_path):
    store, conn = _setup(tmp_path)
    reindex(store, conn, HashingEmbedder(dim=64))
    db.meta_set(conn, "indexed_schema", "3")  # simulate a DB built by an older torsor
    conn.commit()
    stats = reindex(store, conn, HashingEmbedder(dim=64))
    assert stats["indexed"] == stats["total"]  # format change forces one full rebuild
    assert db.meta_get(conn, "indexed_schema") == str(db.SCHEMA_VERSION)


def test_wikilink_edges_resolve_regardless_of_index_order(tmp_path):
    store, conn = _setup(tmp_path)
    a = store.paths.journal_dir / "aaa.md"
    z = store.paths.journal_dir / "zzz.md"
    a.parent.mkdir(parents=True, exist_ok=True)
    a.write_text("---\ntype: note\n---\n\n# A\n\nsee [[zzz]]\n")
    z.write_text("---\ntype: note\n---\n\n# Z\n\nzzz body\n")
    reindex(store, conn, HashingEmbedder(dim=64))
    # aaa sorts before zzz, so insert-time resolution alone would miss this edge
    assert db.neighbors(conn, str(a)) == [str(z)]


def test_wikilink_edges_heal_when_target_created_later(tmp_path):
    store, conn = _setup(tmp_path)
    a = store.paths.journal_dir / "aaa.md"
    a.parent.mkdir(parents=True, exist_ok=True)
    a.write_text("---\ntype: note\n---\n\n# A\n\nsee [[zzz]]\n")
    reindex(store, conn, HashingEmbedder(dim=64))
    assert db.neighbors(conn, str(a)) == []
    z = store.paths.journal_dir / "zzz.md"
    z.write_text("---\ntype: note\n---\n\n# Z\n\nzzz body\n")
    reindex(store, conn, HashingEmbedder(dim=64))  # incremental: aaa itself unchanged
    assert db.neighbors(conn, str(a)) == [str(z)]


def test_slug_resolution_is_literal_not_like_pattern(tmp_path):
    conn = db.connect(tmp_path / "i.db")
    db.upsert_note(conn, "notes/myXnote.md", "h", 4, "note", None, "t", "")
    db.replace_edges(conn, "src.md", ["my_note"])  # '_' must not act as a wildcard
    assert db.neighbors(conn, "src.md") == []


def test_connect_enables_wal_and_busy_timeout(tmp_path):
    conn = db.connect(tmp_path / "i.db")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000


def test_reindex_skips_unchanged_notes_without_reading(tmp_path, monkeypatch):
    store, conn = _setup(tmp_path)
    reindex(store, conn, HashingEmbedder(dim=64))
    reads = []
    orig = store.read_note
    monkeypatch.setattr(store, "read_note", lambda p: (reads.append(p), orig(p))[1])
    stats = reindex(store, conn, HashingEmbedder(dim=64))
    assert stats["indexed"] == 0
    assert reads == []  # stat pre-screen: unchanged notes are never even read


def test_reindex_rewrite_with_same_content_skips_reembed(tmp_path):
    import os

    store, conn = _setup(tmp_path)
    reindex(store, conn, HashingEmbedder(dim=64))
    charter = store.paths.charter
    charter.write_text(charter.read_text(encoding="utf-8"), encoding="utf-8")  # touch, same bytes
    os.utime(charter, ns=(1, 1))  # force a different mtime
    stats = reindex(store, conn, HashingEmbedder(dim=64))
    assert stats["indexed"] == 0  # hash check still skips; stat columns refreshed
    stats = reindex(store, conn, HashingEmbedder(dim=64))
    assert stats["indexed"] == 0
