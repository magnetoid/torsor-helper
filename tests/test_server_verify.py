import json

import anyio

from torsor_helper.server import build_server


def test_verify_and_stale_are_registered(tmp_path):
    tools = anyio.run(build_server(tmp_path).list_tools)
    names = {t.name for t in tools}
    assert {"verify", "stale"} <= names


def test_verify_tool_returns_json_verdict(tmp_path):
    from typer.testing import CliRunner

    from torsor_helper.cli import app

    CliRunner().invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "ok.py").write_text("import os\n")
    server = build_server(tmp_path)
    tools = {t.name: t for t in anyio.run(server.list_tools)}
    result = anyio.run(lambda: server.call_tool("verify", {"files": ["ok.py"]}))
    # FastMCP returns (content, ...); the JSON verdict is in the text payload.
    payload = result[0][0].text if isinstance(result, tuple) else result[0].text
    verdict = json.loads(payload)
    assert verdict["ok"] is True
    assert "checks" in verdict
    assert "verify" in tools
