from datetime import datetime

from torsor_helper import db
from torsor_helper.coach.recommender import best_practice_recs
from torsor_helper.config import TorsorConfig
from torsor_helper.embeddings import HashingEmbedder
from torsor_helper.indexer import reindex
from torsor_helper.models import Symbol
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _indexed(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    store.append_journal("Learned: cache the embedder per process", kind="learning", links=[])
    conn = db.connect(tmp_path / "idx.db")
    reindex(store, conn, HashingEmbedder(dim=128))
    db.replace_all_symbols(conn, [
        Symbol(name="format_date", kind="function", signature="format_date(d)", module="utils/dates.py", line=12, doc="Format.", refs=3),
    ])
    return store, conn


def test_reuse_rec_from_symbol_inventory(tmp_path):
    store, conn = _indexed(tmp_path)
    recs = best_practice_recs(store, TorsorConfig(), "format date", conn=conn, embedder=HashingEmbedder(dim=128))
    reuse = [r for r in recs if r.kind == "reuse"]
    assert reuse
    assert "format_date(d)" in reuse[0].message
    assert reuse[0].source == "utils/dates.py:12"


def test_no_conn_returns_empty(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    assert best_practice_recs(store, TorsorConfig(), "anything", conn=None, embedder=None) == []
