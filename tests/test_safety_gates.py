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
    assert "run_tests" not in (verify.input_schema.get("properties") or {})


def test_the_cli_can_still_run_them(tmp_path):
    _project(tmp_path)
    res = runner.invoke(app, ["verify", "--root", str(tmp_path), "--run-tests"])
    assert res.exit_code in (0, 1)   # runs; a missing `test` command is a skip


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
