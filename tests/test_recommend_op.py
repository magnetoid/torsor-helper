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


def test_recommend_surfaces_hygiene_on_fresh_project(tmp_path):
    store = _store(tmp_path)
    recs = ops.recommend(store, TorsorConfig())
    assert any(r.kind == "thin" for r in recs)


def test_dismiss_recommendation_persists(tmp_path):
    store = _store(tmp_path)
    ops.dismiss_recommendation(store, "thin:charter")
    recs = ops.recommend(store, TorsorConfig())
    assert all(r.key != "thin:charter" for r in recs)
