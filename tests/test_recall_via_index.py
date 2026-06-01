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
    assert store.paths.index_db.exists()


def test_recall_falls_back_to_keyword_when_index_disabled(tmp_path):
    store = _store(tmp_path)
    ops.remember(store, "fallback keyword path works", kind="observation", links=[])
    cfg = TorsorConfig()
    cfg.index.auto_index = False
    res = ops.recall(store, cfg, "fallback keyword")
    assert any("fallback" in h.snippet for h in res.hits)
    assert not store.paths.index_db.exists()
