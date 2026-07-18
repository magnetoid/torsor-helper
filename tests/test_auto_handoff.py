from datetime import datetime
from pathlib import Path
import subprocess

from torsor_helper import operations as ops
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


def _seed_marker(store, root):
    # Baseline the capture marker exactly as install_hooks does, so the scaffold's
    # starter ADR isn't mistaken for new-this-session work.
    ops._save_capture_state(store, {
        "last_head": ops._git_head(root),
        "op_snapshot": ops._op_totals(store),
        "adr_max": ops._next_adr_number(store) - 1,
    })


def test_auto_handoff_writes_deterministic_digest(tmp_path):
    store = _repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-m", "first")
    _seed_marker(store, tmp_path)

    (tmp_path / "a.py").write_text("x = 2\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-m", "second change")

    path = ops.auto_handoff(store, TorsorConfig())
    assert path is not None
    body = Path(path).read_text()
    assert "handoff" in body
    assert "second change" in body  # commit subject appears in the digest
    # marker advanced to the new HEAD
    assert ops._load_capture_state(store)["last_head"] == ops._git_head(tmp_path)


def test_auto_handoff_noop_when_nothing_changed(tmp_path):
    store = _repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-m", "first")
    _seed_marker(store, tmp_path)
    assert ops.auto_handoff(store, TorsorConfig()) is None


def test_auto_handoff_respects_flag(tmp_path):
    store = _repo(tmp_path)
    cfg = TorsorConfig()
    cfg.automation.auto_handoff = False
    assert ops.auto_handoff(store, cfg) is None


def test_auto_handoff_includes_open_questions_and_next_steps(tmp_path):
    store = _repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-m", "first")
    _seed_marker(store, tmp_path)
    ops.update_active(store, focus="ship hooks", progress="wired post-commit", open_questions="test on CI?")
    (tmp_path / "a.py").write_text("x = 2\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-m", "second")

    body = Path(ops.auto_handoff(store, TorsorConfig())).read_text()
    assert "test on CI?" in body  # from active-context Open questions
    assert "wired post-commit" in body  # from progress note
