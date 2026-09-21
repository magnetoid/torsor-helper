"""The two adapters expose the same features with the same controls.

Nothing tied them together, so they drifted: `find` could restrict to files or
symbols from the CLI but not over MCP, `stale` could unmark from the CLI but
not over MCP, `guard` had --update-baseline on one side and new_only on the
other, and `deps` returned prose over MCP with no way to tell pass from fail.
"""
from __future__ import annotations

import anyio
import pytest
from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.paths import TorsorPaths
from torsor_helper.server import build_server
from torsor_helper.store import Store

runner = CliRunner()


@pytest.fixture
def tools(tmp_path):
    Store(TorsorPaths(tmp_path)).scaffold()
    return {t.name: set((t.inputSchema.get("properties") or {})) for t in
            anyio.run(build_server(tmp_path).list_tools)}


def _cli_options(command: str) -> set[str]:
    out = runner.invoke(app, [command, "--help"]).output
    return {tok.lstrip("-").replace("-", "_")
            for tok in out.split() if tok.startswith("--") and len(tok) > 2}


@pytest.mark.parametrize("tool, cli, shared", [
    ("find_files", "find", {"limit", "mode"}),
    ("stale", "stale", {"mark", "unmark"}),
    ("recall", "recall", {"limit", "kind"}),
    ("map_repo", "map", {"force"}),
    ("check_drift", "guard", {"new_only"}),
])
def test_a_feature_offers_the_same_controls_on_both_surfaces(tools, tool, cli, shared):
    assert shared <= tools[tool], f"{tool} is missing {shared - tools[tool]}"
    assert shared <= _cli_options(cli), f"torsor {cli} is missing {shared - _cli_options(cli)}"


def test_find_can_be_restricted_to_files_or_symbols_over_mcp(tools):
    assert {"include_files", "include_symbols"} <= tools["find_files"]


def test_map_can_be_scoped_to_paths_from_the_cli():
    assert "paths" in _cli_options("map") or "path" in _cli_options("map")


def test_check_dependencies_reports_a_failure_signal(tmp_path):
    """It returned prose, so a gate could not tell "clean" from "three phantom
    imports" without parsing English."""
    import json

    Store(TorsorPaths(tmp_path)).scaffold()
    (tmp_path / "bad.py").write_text("import deffinitely_not_real\n")
    server = build_server(tmp_path)

    out = anyio.run(lambda: server.call_tool("check_dependencies",
                                             {"files": ["bad.py"], "as_json": True}))
    content = out[0] if isinstance(out, tuple) else out
    payload = json.loads(content[0].text)

    assert payload["ok"] is False
    assert payload["count"] >= 1


def test_a_recommendation_can_be_dismissed_over_mcp(tools):
    assert "dismiss_recommendation" in tools


def test_the_server_exposes_the_prompts_the_foundation_spec_designed(tmp_path):
    """Prompts are how an MCP client renders slash-commands, so the loop steps
    stop depending on the agent remembering which tool to call in which order.
    Specified at the start of the project and never built."""
    Store(TorsorPaths(tmp_path)).scaffold()
    prompts = {p.name for p in anyio.run(build_server(tmp_path).list_prompts)}
    assert {"onboard", "checkpoint", "review_drift", "coach"} <= prompts


def test_the_architecture_and_map_are_readable_as_resources(tmp_path):
    Store(TorsorPaths(tmp_path)).scaffold()
    uris = {str(r.uri) for r in anyio.run(build_server(tmp_path).list_resources)}
    assert {"torsor://charter", "torsor://active",
            "torsor://architecture", "torsor://map/overview"} <= uris


def test_a_prompt_on_an_uninitialized_project_says_so(tmp_path):
    server = build_server(tmp_path / "nope")
    result = anyio.run(lambda: server.get_prompt("onboard", {}))
    assert "torsor init" in str(result).lower()
