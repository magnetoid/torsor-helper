"""Gates on the operations that are hard to undo or that reach outside torsor.

Each one exists because the default was "do it and mention it afterwards".
"""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.config import TorsorConfig, load_config, save_config
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def _project(tmp_path):
    Store(TorsorPaths(tmp_path)).scaffold()
    return tmp_path


# --- command execution is CLI-only (ADR 0009's reasoning, applied) ---------

def test_the_mcp_verify_tool_cannot_run_recorded_shell_commands(tmp_path):
    import anyio

    from torsor_helper.server import build_server

    _project(tmp_path)
    server = build_server(tmp_path)
    tools = anyio.run(server.list_tools)

    verify = next(t for t in tools if t.name == "verify")
    assert "run_tests" not in (verify.inputSchema.get("properties") or {})


def test_the_cli_can_still_run_them(tmp_path):
    _project(tmp_path)
    res = runner.invoke(app, ["verify", "--root", str(tmp_path), "--run-tests"])
    assert res.exit_code in (0, 1)   # runs; a missing `test` command is a skip


# --- an unauthenticated server does not go on a routable interface by accident

@pytest.fixture
def no_server(monkeypatch):
    """Never let a test actually bind a port — the point is the gate in front."""
    calls = []
    monkeypatch.setattr("torsor_helper.server.run", lambda *a, **k: calls.append(k))
    return calls


def test_http_on_a_non_loopback_host_refuses_without_an_explicit_opt_in(tmp_path, no_server):
    _project(tmp_path)
    res = runner.invoke(app, ["mcp", "--root", str(tmp_path), "--http", "--host", "0.0.0.0"])
    assert res.exit_code == 2
    assert "--allow-remote" in res.output
    assert no_server == []   # and it must not have served anyway


def test_a_non_loopback_host_serves_once_the_opt_in_is_explicit(tmp_path, no_server):
    _project(tmp_path)
    res = runner.invoke(app, ["mcp", "--root", str(tmp_path), "--http", "--host", "0.0.0.0", "--allow-remote"])
    assert res.exit_code == 0
    assert no_server[0]["host"] == "0.0.0.0"


def test_loopback_http_needs_no_opt_in(tmp_path, no_server):
    _project(tmp_path)
    res = runner.invoke(app, ["mcp", "--root", str(tmp_path), "--http"])
    assert res.exit_code == 0
    assert no_server[0]["host"] == "127.0.0.1"


# --- the only irreversible cleanup asks first ------------------------------

def test_clean_apply_deep_refuses_without_yes(tmp_path):
    _project(tmp_path)
    res = runner.invoke(app, ["clean", "--root", str(tmp_path), "--apply", "--deep"])
    assert res.exit_code == 2
    assert "--yes" in res.output


def test_clean_apply_without_deep_needs_no_yes(tmp_path):
    _project(tmp_path)
    res = runner.invoke(app, ["clean", "--root", str(tmp_path), "--apply"])
    assert res.exit_code == 0


# --- a typo in torsor.toml is an error, not a silent default ---------------

def test_an_unknown_config_key_is_rejected(tmp_path):
    paths = TorsorPaths(_project(tmp_path))
    paths.config_file.write_text("version = 1\n\n[automaton]\nauto_handoff = false\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(paths)


def test_an_invalid_guard_on_edit_mode_is_rejected(tmp_path):
    paths = TorsorPaths(_project(tmp_path))
    paths.config_file.write_text("version = 1\n\n[automation]\nguard_on_edit = \"blok\"\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(paths)


def test_doctor_names_the_offending_key(tmp_path):
    paths = TorsorPaths(_project(tmp_path))
    paths.config_file.write_text("version = 1\n\n[automaton]\nauto_handoff = false\n", encoding="utf-8")
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert res.exit_code == 1
    assert "automaton" in res.output


def test_a_valid_config_still_round_trips(tmp_path):
    paths = TorsorPaths(_project(tmp_path))
    cfg = TorsorConfig()
    cfg.automation.guard_on_edit = "block"
    save_config(paths, cfg)
    assert load_config(paths).automation.guard_on_edit == "block"
