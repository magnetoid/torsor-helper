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
