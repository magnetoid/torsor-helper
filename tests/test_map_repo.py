from datetime import datetime

from torsor_helper import db, operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _project(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    (tmp_path / "app.py").write_text(
        "def format_date(d):\n    return d\n\nclass Service:\n    def handle(self, req):\n        return req\n"
    )
    return store


def test_map_repo_writes_map_and_stores_symbols(tmp_path):
    store = _project(tmp_path)
    stats = ops.map_repo(store, TorsorConfig())
    assert stats["symbols"] >= 3
    assert stats["modules"] >= 1
    assert store.paths.map_overview.exists()
    assert "app.py" in store.paths.map_overview.read_text()
    conn = db.connect(store.paths.index_db)
    try:
        assert any(s.name == "format_date" for s in db.search_symbols(conn, "format_date"))
        assert "app.py" in db.modules(conn)
    finally:
        conn.close()


def test_map_repo_is_repeatable(tmp_path):
    store = _project(tmp_path)
    ops.map_repo(store, TorsorConfig())
    ops.map_repo(store, TorsorConfig())
    conn = db.connect(store.paths.index_db)
    try:
        fmt = db.search_symbols(conn, "format_date")
        assert len([s for s in fmt if s.name == "format_date"]) == 1
    finally:
        conn.close()
