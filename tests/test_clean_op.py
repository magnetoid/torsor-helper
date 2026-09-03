from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 0, 0)


def _project(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    (tmp_path / "gone.py").write_text("def dropped():\n    return 2\n", encoding="utf-8")
    ops.map_repo(store, TorsorConfig())
    (tmp_path / "gone.py").unlink()
    return store


def test_clean_dry_run_reports_without_deleting(tmp_path):
    store = _project(tmp_path)
    orphan = store.paths.map_dir / "modules" / "gone.py.md"

    stats = ops.clean(store, TorsorConfig())

    assert stats["dry_run"] is True
    assert stats["map_orphans"] == 1
    assert orphan.exists()


def test_clean_apply_deletes_and_reports_what_it_reclaimed(tmp_path):
    store = _project(tmp_path)
    orphan = store.paths.map_dir / "modules" / "gone.py.md"
    size = orphan.stat().st_size

    stats = ops.clean(store, TorsorConfig(), apply=True)

    assert stats["dry_run"] is False
    assert stats["map_orphans"] == 1
    assert stats["reclaimed_bytes"] >= size
    assert not orphan.exists()
