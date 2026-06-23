from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 23, 9, 0, 0)


def _repo(tmp_path):
    """A directed call chain across three modules: top -> middle -> bottom."""
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    (tmp_path / "store_mod.py").write_text("def bottom():\n    return 1\n")
    (tmp_path / "svc.py").write_text(
        "from store_mod import bottom\n\ndef middle():\n    return bottom()\n"
    )
    (tmp_path / "app.py").write_text(
        "from svc import middle\n\ndef top():\n    return middle()\n"
    )
    return store


def test_connect_finds_directed_path(tmp_path):
    store = _repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    res = ops.connect(store, TorsorConfig(), "top", "bottom")
    assert res["found"] is True
    assert [step["symbol"] for step in res["path"]] == ["top", "middle", "bottom"]
    assert res["hops"] == 2


def test_connect_is_directed_no_reverse_path(tmp_path):
    store = _repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    res = ops.connect(store, TorsorConfig(), "bottom", "top")
    assert res["found"] is False
    assert res["path"] == []


def test_connect_same_symbol_is_zero_hops(tmp_path):
    store = _repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    res = ops.connect(store, TorsorConfig(), "top", "top")
    assert res["found"] is True
    assert res["hops"] == 0
    assert [step["symbol"] for step in res["path"]] == ["top"]


def test_connect_unknown_symbol_is_empty(tmp_path):
    store = _repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    res = ops.connect(store, TorsorConfig(), "top", "nonexistent")
    assert res["found"] is False
    assert res["path"] == []


def test_connect_without_index_is_empty(tmp_path):
    store = _repo(tmp_path)
    # no map_repo -> no index
    res = ops.connect(store, TorsorConfig(), "top", "bottom")
    assert res["found"] is False
    assert res["path"] == []
