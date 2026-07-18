from datetime import datetime
import subprocess

from torsor_helper import db, operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 7, 18, 10, 0, 0)


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _repo(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.t")
    _git(tmp_path, "config", "user.name", "t")
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_on_commit_maps_changed_and_preserves_other_modules(tmp_path):
    store = _repo(tmp_path)
    (tmp_path / "a.py").write_text("def alpha():\n    return 1\n")
    (tmp_path / "b.py").write_text("def beta():\n    return 2\n")
    _git(tmp_path, "add", "a.py", "b.py")
    _git(tmp_path, "commit", "-m", "add a b")
    ops.map_repo(store, TorsorConfig())  # full seed

    (tmp_path / "a.py").write_text("def alpha():\n    return 1\n\ndef gamma():\n    return 3\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-m", "add gamma")

    result = ops.on_commit(store, TorsorConfig())
    assert "a.py" in result["mapped"]
    assert result["snapshot"] is True

    conn = db.connect(store.paths.index_db)
    try:
        mods = db.modules(conn)
        names = {s["name"] for s in db.all_symbols(conn)}
    finally:
        conn.close()
    assert "a.py" in mods and "b.py" in mods  # partial merge preserved b.py (ADR 0008)
    assert "gamma" in names  # a.py rescanned


def test_on_commit_respects_flags(tmp_path):
    store = _repo(tmp_path)
    (tmp_path / "a.py").write_text("def alpha():\n    return 1\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-m", "a")
    ops.map_repo(store, TorsorConfig())

    cfg = TorsorConfig()
    cfg.automation.auto_map_on_commit = False
    cfg.automation.auto_snapshot_on_commit = False
    (tmp_path / "a.py").write_text("def alpha():\n    return 9\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-m", "a2")

    result = ops.on_commit(store, cfg)
    assert result["mapped"] == []
    assert result["snapshot"] is False


def test_on_commit_noop_when_no_source_files(tmp_path):
    store = _repo(tmp_path)
    (tmp_path / "README.txt").write_text("hi\n")
    _git(tmp_path, "add", "README.txt")
    _git(tmp_path, "commit", "-m", "docs")
    result = ops.on_commit(store, TorsorConfig())
    assert result["mapped"] == []
    assert result["snapshot"] is False
