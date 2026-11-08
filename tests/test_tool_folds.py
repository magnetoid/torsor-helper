"""The MCP surface after ADR 0019's second pass: fifteen tools, each a distinct
moment in the loop. Three ways to "load the project" became one tool with a
topic switch, three drift checks became `verify`, the call-path query became a
parameter of `impact`, and the operator actions (stats, clean, hooks_status)
left the agent-facing surface for the CLI."""
import anyio
from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.server import build_server
from torsor_helper.store import Store

runner = CliRunner()

EXPECTED_TOOLS = {
    "bootstrap_session", "recall", "remember", "update_active", "handoff",
    "map_repo", "impact", "get_rules", "record_command", "list_commands",
    "record_decision", "check_dependencies", "verify",
    "recommend", "dismiss_recommendation",
}


def _tools(root):
    return {t.name: t for t in anyio.run(build_server(root).list_tools)}


def _params(tool):
    return set(tool.input_schema.get("properties") or {})


def _call(server, name, **kwargs):
    return anyio.run(lambda: server.call_tool(name, kwargs)).content[0].text


def test_the_tool_list_is_exactly_the_fifteen(tmp_path):
    Store(TorsorPaths(tmp_path)).scaffold()
    assert set(_tools(tmp_path)) == EXPECTED_TOOLS


def test_bootstrap_session_takes_a_topic_instead_of_a_separate_intent_tool(tmp_path):
    (tmp_path / "pay.py").write_text("def charge_card():\n    return 1\n", encoding="utf-8")
    Store(TorsorPaths(tmp_path)).scaffold()
    runner.invoke(app, ["map", "--root", str(tmp_path)])
    server = build_server(tmp_path)
    tools = _tools(tmp_path)

    assert "topic" in _params(tools["bootstrap_session"])
    plain = _call(server, "bootstrap_session")
    focused = _call(server, "bootstrap_session", topic="charge card")
    assert "charge_card" in focused
    assert focused != plain


def test_impact_answers_how_x_reaches_y_instead_of_a_separate_connect_tool(tmp_path):
    (tmp_path / "a.py").write_text("def leaf():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("from a import leaf\n\ndef mid():\n    return leaf()\n", encoding="utf-8")
    (tmp_path / "c.py").write_text("from b import mid\n\ndef top():\n    return mid()\n", encoding="utf-8")
    Store(TorsorPaths(tmp_path)).scaffold()
    runner.invoke(app, ["map", "--root", str(tmp_path)])
    server = build_server(tmp_path)

    assert "to" in _params(_tools(tmp_path)["impact"])
    path = _call(server, "impact", symbol="top", to="leaf")
    assert "hop" in path and "mid" in path
    assert "reference" in _call(server, "impact", symbol="leaf")


def test_verify_is_the_only_drift_check_over_mcp(tmp_path):
    Store(TorsorPaths(tmp_path)).scaffold()
    (tmp_path / "ok.py").write_text("import os\n", encoding="utf-8")
    tools = _tools(tmp_path)
    assert {"files", "severity"} <= _params(tools["verify"])
    # The same controls on the CLI: the CLI test in test_surface_parity covers
    # the option names; here, only that the verdict still composes the three.
    verdict = _call(build_server(tmp_path), "verify", files=["ok.py"])
    assert {"guard", "deps", "staleness"} <= {c["name"] for c in __import__("json").loads(verdict)["checks"]}


def test_operator_actions_stay_on_the_cli(tmp_path):
    Store(TorsorPaths(tmp_path)).scaffold()
    names = set(_tools(tmp_path))
    assert not {"stats", "clean", "hooks_status", "stale", "check_drift", "connect", "get_intent", "get_primer"} & names
    for argv in (["stats"], ["clean"], ["hooks", "status"], ["stale"], ["guard"], ["connect", "a", "b"],
                 ["intent"], ["primer"]):
        result = runner.invoke(app, [*argv, "--root", str(tmp_path)])
        assert result.exit_code == 0, (argv, result.output)
    # and the operations stay, so nothing above is a feature cut
    assert all(hasattr(ops, n) for n in ("stats", "clean", "hooks_status", "check_staleness", "check_drift",
                                           "connect", "get_intent", "project_primer"))


def test_the_onboard_prompt_still_loads_the_project(tmp_path):
    Store(TorsorPaths(tmp_path)).scaffold()
    result = anyio.run(lambda: build_server(tmp_path).get_prompt("onboard", {}))
    text = result.messages[0].content.text
    assert "memory" in text.lower()
    assert TorsorConfig().budgets.intent_tokens > 0
