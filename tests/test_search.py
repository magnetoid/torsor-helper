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
    assert all(h.tier.name == "EPISODIC" for h in res.hits)


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
