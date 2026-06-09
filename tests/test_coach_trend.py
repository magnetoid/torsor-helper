from datetime import datetime

from torsor_helper import db
from torsor_helper import operations as ops
from torsor_helper.coach import trend
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 10, 9, 0, 0)

_COMPLEX = "def f(x):\n" + "".join(f"    if x == {i}:\n        return {i}\n" for i in range(10)) + "    return -1\n"


def test_snapshot_roundtrip_and_replace(tmp_path):
    conn = db.connect(tmp_path / "i.db")
    db.save_complexity_snapshot(conn, {"h.py": 10, "c.py": 3})
    assert db.load_complexity_snapshot(conn) == {"h.py": 10, "c.py": 3}
    db.save_complexity_snapshot(conn, {"h.py": 20})  # replace-all
    assert db.load_complexity_snapshot(conn) == {"h.py": 20}


def test_find_regressions_flags_complexity_rise(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    (tmp_path / "h.py").write_text("def f():\n    return 1\n")
    conn = db.connect(store.paths.index_db)
    db.save_complexity_snapshot(conn, {"h.py": 3})  # low baseline
    (tmp_path / "h.py").write_text(_COMPLEX)  # complexity jumps
    try:
        recs = trend.find_regressions(tmp_path, conn)
    finally:
        conn.close()
    assert any(r.kind == "regression" and r.source == "h.py" for r in recs)


def test_no_regression_without_baseline(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    (tmp_path / "h.py").write_text(_COMPLEX)
    conn = db.connect(store.paths.index_db)
    try:
        assert trend.find_regressions(tmp_path, conn) == []  # no snapshot → nothing is a regression
    finally:
        conn.close()


def test_no_regression_when_unchanged(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    (tmp_path / "h.py").write_text(_COMPLEX)
    conn = db.connect(store.paths.index_db)
    snap = trend.current_complexity(tmp_path)
    db.save_complexity_snapshot(conn, snap)
    try:
        assert trend.find_regressions(tmp_path, conn) == []
    finally:
        conn.close()


def test_consolidate_writes_complexity_snapshot(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    (tmp_path / "h.py").write_text("def f():\n    if True:\n        return 1\n")
    ops.consolidate(store, TorsorConfig())
    conn = db.connect(store.paths.index_db)
    try:
        assert "h.py" in db.load_complexity_snapshot(conn)
    finally:
        conn.close()
