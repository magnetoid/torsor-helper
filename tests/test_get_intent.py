from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _project(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_get_intent_returns_architecture(tmp_path):
    store = _project(tmp_path)
    out = ops.get_intent(store, TorsorConfig())
    assert "## System Patterns" in out
    assert "## Tech Context" in out
    assert "## Decisions" in out


def test_get_intent_with_topic_surfaces_relevant_symbols(tmp_path):
    store = _project(tmp_path)
    (store.paths.root / "app.py").write_text("def format_date(d):\n    return d\n")
    ops.map_repo(store, TorsorConfig())
    out = ops.get_intent(store, TorsorConfig(), topic="format date")
    assert "Relevant existing symbols" in out
    assert "format_date(d)" in out
