"""What each adapter promises, where the two used to disagree.

The MCP server served 28 tools on an uninitialized project, all returning
empty strings; it read torsor.toml once at startup, so a long-lived server
never saw a config change; and adopt_practices returned prose, so a caller
could not tell success from "unknown pack".
"""
from __future__ import annotations

import json

import anyio
from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.config import load_config, save_config
from torsor_helper.paths import TorsorPaths
from torsor_helper.server import build_server
from torsor_helper.store import Store

runner = CliRunner()


def _project(tmp_path):
    Store(TorsorPaths(tmp_path)).scaffold()
    return tmp_path


def _call(server, name, **kwargs):
    return anyio.run(lambda: server.call_tool(name, kwargs))


# --- the server must say what is wrong, not serve emptiness -----------------

def test_a_tool_on_an_uninitialized_project_says_so(tmp_path):
    server = build_server(tmp_path / "nope")
    result = _call(server, "get_rules")
    assert "torsor init" in str(result).lower()


def test_a_malformed_config_is_reported_per_call_not_at_import(tmp_path):
    root = _project(tmp_path)
    (root / ".torsor" / "torsor.toml").write_text("version = 1\n\n[automaton]\nx = 1\n", encoding="utf-8")

    server = build_server(root)          # must not raise
    result = _call(server, "get_rules")

    assert "torsor.toml" in str(result)


def test_a_config_change_is_picked_up_without_a_restart(tmp_path):
    root = _project(tmp_path)
    server = build_server(root)
    _call(server, "get_rules")

    config = load_config(TorsorPaths(root))
    config.models.cheap = "haiku-x"
    save_config(TorsorPaths(root), config)

    assert "haiku-x" in str(_call(server, "get_model_policy"))


# --- a result a caller can branch on ---------------------------------------

def _text(out):
    """The text a FastMCP tool returned."""
    content = out[0] if isinstance(out, tuple) else out
    return content[0].text


def test_adopt_practices_reports_failure_distinguishably(tmp_path):
    """It returned prose, so a caller could not tell "adopted" from "unknown
    pack" from "already adopted" — all three were a success-shaped string."""
    root = _project(tmp_path)
    server = build_server(root)

    ok = json.loads(_text(_call(server, "adopt_practices", language="python")))
    bad = json.loads(_text(_call(server, "adopt_practices", language="klingon")))

    assert ok["adopted"] is True and ok["path"]
    assert bad["adopted"] is False and "klingon" in bad["message"]


# --- flags with one name and two meanings ----------------------------------

def test_models_write_json_is_its_own_flag(tmp_path):
    root = _project(tmp_path)
    target = tmp_path / "policy.json"
    target.write_text('{"keep": "me"}\n', encoding="utf-8")

    # --write on a .json used to silently overwrite the whole file
    result = runner.invoke(app, ["models", "--root", str(root), "--write", str(target)])
    assert result.exit_code == 2
    assert json.loads(target.read_text())["keep"] == "me"

    assert runner.invoke(app, ["models", "--root", str(root), "--write-json", str(target)]).exit_code == 0
    assert "cheap" in json.loads(target.read_text())


def test_rules_scoped_refuses_a_conflicting_target(tmp_path):
    root = _project(tmp_path)
    result = runner.invoke(app, ["rules", "--root", str(root), "--scoped", "--write", "AGENTS.md"])
    assert result.exit_code == 2
    assert "scoped" in result.output.lower()


def test_commands_add_takes_two_arguments(tmp_path):
    root = _project(tmp_path)
    result = runner.invoke(app, ["commands", "--root", str(root), "--add", "test", "uv run pytest -q"])
    assert result.exit_code == 0, result.output
    assert "uv run pytest -q" in runner.invoke(app, ["commands", "--root", str(root)]).output


def test_a_command_containing_an_equals_sign_survives(tmp_path):
    root = _project(tmp_path)
    runner.invoke(app, ["commands", "--root", str(root), "--add", "env", "FOO=bar uv run pytest"])
    assert "FOO=bar" in runner.invoke(app, ["commands", "--root", str(root)]).output
