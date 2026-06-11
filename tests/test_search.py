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


def test_filter_reaches_matches_beyond_default_pool(tmp_path):
    # A selective filter must not return empty just because the only matching
    # note ranks below the unfiltered candidate pool (limit*4).
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    for i in range(40):  # 40 high-scoring journal notes crowd the pool
        (store.paths.journal_dir / f"n{i:02d}.md").write_text(
            f"---\ntype: journal\n---\n\n# Note {i}\n\n{'alpha ' * 20}\n"
        )
    (store.paths.decisions_dir / "0099-alpha.md").write_text(
        "---\ntype: decision\nstatus: accepted\n---\n\n# ADR 0099: alpha\n\n"
        "We decided alpha handling lives in one module, among much other prose "
        "that dilutes the term so this note ranks below the journal flood.\n"
    )
    conn = db.connect(tmp_path / "idx.db")
    reindex(store, conn, HashingEmbedder(dim=128))
    res = hybrid_search(conn, HashingEmbedder(dim=128), TorsorConfig(), "alpha", type_="decision")
    assert any("0099-alpha" in h.path for h in res.hits)
