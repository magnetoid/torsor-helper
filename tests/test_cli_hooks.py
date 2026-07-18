import json
import subprocess

from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app

runner = CliRunner()


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _init_repo(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.t")
    _git(tmp_path, "config", "user.name", "t")
    runner.invoke(app, ["init", "--root", str(tmp_path)])


def test_install_status_uninstall_roundtrip(tmp_path):
    _init_repo(tmp_path)

    r = runner.invoke(app, ["hooks", "install", "--root", str(tmp_path)])
    assert r.exit_code == 0
    assert (tmp_path / ".git" / "hooks" / "post-commit").exists()
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert "SessionEnd" in settings["hooks"]

    status = runner.invoke(app, ["hooks", "status", "--root", str(tmp_path)])
    assert "post-commit: installed" in status.stdout
    assert "SessionEnd" in status.stdout

    r = runner.invoke(app, ["hooks", "uninstall", "--root", str(tmp_path)])
    assert r.exit_code == 0
    assert not (tmp_path / ".git" / "hooks" / "post-commit").exists()


def test_install_warns_outside_git_repo(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])  # no git init
    r = runner.invoke(app, ["hooks", "install", "--root", str(tmp_path)])
    assert r.exit_code == 0
    assert "not a git repo" in r.stdout or "not a git repo" in (r.stderr or "")


def test_run_session_end_dispatches_to_auto_handoff(tmp_path, monkeypatch):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    called = {}
    monkeypatch.setattr(ops, "auto_handoff", lambda *a, **k: called.setdefault("hit", True))
    payload = json.dumps({"session_id": "s1", "transcript_path": "/tmp/x.jsonl"})
    r = runner.invoke(app, ["hooks", "run", "session-end", "--root", str(tmp_path)], input=payload)
    assert r.exit_code == 0
    assert called.get("hit") is True


def test_run_post_commit_dispatches_to_on_commit(tmp_path, monkeypatch):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    called = {}
    monkeypatch.setattr(ops, "on_commit", lambda *a, **k: called.setdefault("hit", True) or {})
    r = runner.invoke(app, ["hooks", "run", "post-commit", "--root", str(tmp_path)])
    assert r.exit_code == 0
    assert called.get("hit") is True


def test_run_is_noop_without_torsor_project(tmp_path):
    # The dispatcher must never break the git/agent lifecycle on an uninitialized dir.
    r = runner.invoke(app, ["hooks", "run", "post-commit", "--root", str(tmp_path)])
    assert r.exit_code == 0
