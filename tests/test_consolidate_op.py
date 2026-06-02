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
    assert stats["indexed"] >= 1  # freshly-mined insights are indexed (not always 0)
    assert (store.paths.insights_dir / "learning.md").exists()


def test_consolidate_insight_is_recallable(tmp_path):
    store = _store(tmp_path)
    store.append_journal("cache the embedder per process", kind="learning", links=[])
    ops.consolidate(store, TorsorConfig())
    res = ops.recall(store, TorsorConfig(), "embedder cache")
    assert any("embedder" in h.snippet for h in res.hits)


def test_consolidate_reports_top_accessed(tmp_path):
    store = _store(tmp_path)
    store.append_journal("SQLite chosen for the index", kind="decision", links=[])
    ops.recall(store, TorsorConfig(), "SQLite index")  # bumps access_count on hits
    stats = ops.consolidate(store, TorsorConfig())
    assert "top_accessed" in stats
    assert any(n >= 1 for _path, n in stats["top_accessed"])
