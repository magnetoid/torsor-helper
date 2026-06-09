from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 10, 9, 0, 0)


def _repo(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "dates.py").write_text("def fmt(d):\n    return d\n")
    (tmp_path / "app.py").write_text("from pkg.dates import fmt\n\ndef run():\n    return fmt(1)\n")
    (tmp_path / "cli.py").write_text("from pkg.dates import fmt\n\ndef main():\n    return fmt(2)\n")
    return store


def test_impact_lists_callers_across_files(tmp_path):
    store = _repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    res = ops.impact(store, TorsorConfig(), "fmt")
    assert res["count"] >= 2
    mods = {c["module"] for c in res["callers"]}
    assert {"app.py", "cli.py"} <= mods


def test_impact_unknown_symbol_is_empty(tmp_path):
    store = _repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    res = ops.impact(store, TorsorConfig(), "nonexistent_symbol")
    assert res["count"] == 0
    assert res["callers"] == []


def test_impact_resolves_src_layout(tmp_path):
    # src/ layout: a symbol's file is src/proj/core.py but imports say proj.core —
    # _norm_module must reconcile both so cross-module callers resolve.
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    (tmp_path / "src" / "proj").mkdir(parents=True)
    (tmp_path / "src" / "proj" / "__init__.py").write_text("")
    (tmp_path / "src" / "proj" / "core.py").write_text("def engine():\n    return 1\n")
    (tmp_path / "src" / "proj" / "app.py").write_text("from proj.core import engine\n\ndef run():\n    return engine()\n")
    ops.map_repo(store, TorsorConfig())
    res = ops.impact(store, TorsorConfig(), "engine")
    assert res["count"] >= 1
    assert any(c["module"].endswith("app.py") for c in res["callers"])


def test_impact_no_index_is_empty(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    res = ops.impact(store, TorsorConfig(), "fmt")
    assert res["count"] == 0
