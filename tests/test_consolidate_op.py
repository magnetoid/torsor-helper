from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_consolidate_mines_and_reports(tmp_path):
    store = _store(tmp_path)
    store.append_journal("prefer uv run", kind="learning", links=[])
    store.append_journal("dup", kind="observation", links=[])
    store.append_journal("dup", kind="observation", links=[])
    stats = ops.consolidate(store, TorsorConfig())
    assert stats["insights"] >= 1
    assert stats["duplicates"] >= 1
    assert (store.paths.insights_dir / "learning.md").exists()


def test_consolidate_insight_is_recallable(tmp_path):
    store = _store(tmp_path)
    store.append_journal("cache the embedder per process", kind="learning", links=[])
    ops.consolidate(store, TorsorConfig())
    res = ops.recall(store, TorsorConfig(), "embedder cache")
    assert any("embedder" in h.snippet for h in res.hits)
