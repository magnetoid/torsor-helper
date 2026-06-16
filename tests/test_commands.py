from datetime import datetime

from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()
CLOCK = lambda: datetime(2026, 6, 10, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_record_and_list_roundtrip(tmp_path):
    store = _store(tmp_path)
    ops.record_command(store, "test", "uv run pytest", "run the suite")
    ops.record_command(store, "lint", "ruff check src")
    cmds = {c["name"]: c for c in ops.list_commands(store)}
    assert cmds["test"]["command"] == "uv run pytest"
    assert cmds["test"]["note"] == "run the suite"
    assert cmds["lint"]["command"] == "ruff check src"


def test_record_command_upserts(tmp_path):
    store = _store(tmp_path)
    ops.record_command(store, "test", "old cmd")
    ops.record_command(store, "test", "uv run pytest")
    cmds = ops.list_commands(store)
    matches = [c for c in cmds if c["name"] == "test"]
    assert len(matches) == 1 and matches[0]["command"] == "uv run pytest"


def test_commands_surface_in_primer(tmp_path):
    store = _store(tmp_path)
    ops.record_command(store, "test", "uv run pytest")
    primer = ops.project_primer(store, TorsorConfig())
    assert "uv run pytest" in primer


def test_run_command_executes_and_missing(tmp_path):
    store = _store(tmp_path)
    ops.record_command(store, "ok", "exit 7")  # POSIX shell builtin — portable, no deps
    result = ops.run_command(store, "ok")
    assert result is not None and result.returncode == 7
    assert ops.run_command(store, "nonexistent") is None


def test_cli_commands_add_and_list(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    r = runner.invoke(app, ["commands", "--root", str(tmp_path), "--add", "test=uv run pytest", "--note", "suite"])
    assert r.exit_code == 0, r.output
    out = runner.invoke(app, ["commands", "--root", str(tmp_path)])
    assert "uv run pytest" in out.output and "test" in out.output
