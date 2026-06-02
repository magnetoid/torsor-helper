from datetime import datetime

from torsor_helper import cartographer
from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _project(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    (tmp_path / "app.py").write_text("def run():\n    return 1\n")
    return store


def test_second_map_is_skipped_when_unchanged(tmp_path):
    store = _project(tmp_path)
    first = ops.map_repo(store, TorsorConfig())
    assert first["skipped"] is False
    second = ops.map_repo(store, TorsorConfig())
    assert second["skipped"] is True
    assert second["symbols"] == first["symbols"]  # counts still reported when skipped


def test_change_triggers_rescan(tmp_path):
    store = _project(tmp_path)
    ops.map_repo(store, TorsorConfig())
    (tmp_path / "app.py").write_text("def run():\n    return 1\n\ndef extra():\n    return 2\n")
    after = ops.map_repo(store, TorsorConfig())
    assert after["skipped"] is False
    assert after["symbols"] >= 2


def test_force_always_runs(tmp_path):
    store = _project(tmp_path)
    ops.map_repo(store, TorsorConfig())
    forced = ops.map_repo(store, TorsorConfig(), force=True)
    assert forced["skipped"] is False


def test_explicit_paths_never_skip(tmp_path):
    store = _project(tmp_path)
    ops.map_repo(store, TorsorConfig())
    partial = ops.map_repo(store, TorsorConfig(), paths=["app.py"])
    assert partial["skipped"] is False  # a partial map must not claim the whole repo


def test_fingerprint_changes_with_content(tmp_path):
    _project(tmp_path)
    fp1 = cartographer.repo_fingerprint(tmp_path)
    (tmp_path / "app.py").write_text("def run():\n    return 9999\n")
    fp2 = cartographer.repo_fingerprint(tmp_path)
    assert fp1 != fp2


def test_fingerprint_changes_on_same_size_edit(tmp_path):
    # same byte size, different content — relies on nanosecond mtime (modern FS)
    _project(tmp_path)
    fp1 = cartographer.repo_fingerprint(tmp_path)
    (tmp_path / "app.py").write_text("def run():\n    return 2\n")  # same length as 'return 1'
    assert cartographer.repo_fingerprint(tmp_path) != fp1


def test_full_map_after_partial_rescans(tmp_path):
    # a partial map wipes other modules from the index; a later full map must NOT
    # falsely skip and serve the incomplete graph (regression for the review finding)
    store = _project(tmp_path)
    (tmp_path / "other.py").write_text("def helper():\n    return 2\n")
    ops.map_repo(store, TorsorConfig())                      # full: app.py + other.py
    ops.map_repo(store, TorsorConfig(), paths=["app.py"])    # partial: wipes other.py from index
    after = ops.map_repo(store, TorsorConfig())              # full again must re-scan, not skip
    assert after["skipped"] is False
    from torsor_helper import db
    conn = db.connect(store.paths.index_db)
    try:
        assert "other.py" in db.modules(conn)  # restored
    finally:
        conn.close()
