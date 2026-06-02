import json

from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.clients import mcp_servers_block, write_mcp_json

runner = CliRunner()


def test_mcp_servers_block_shape():
    block = mcp_servers_block("/proj")
    assert block["mcpServers"]["torsor-helper"]["command"] == "torsor"
    assert "/proj" in block["mcpServers"]["torsor-helper"]["args"]


def test_write_mcp_json_creates_file(tmp_path):
    target = write_mcp_json(tmp_path, str(tmp_path))
    assert target == tmp_path / ".mcp.json"
    data = json.loads(target.read_text())
    assert "torsor-helper" in data["mcpServers"]


def test_write_mcp_json_merges_preserving_others(tmp_path):
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    write_mcp_json(tmp_path, str(tmp_path))
    data = json.loads((tmp_path / ".mcp.json").read_text())
    assert "other" in data["mcpServers"]  # existing server preserved
    assert "torsor-helper" in data["mcpServers"]  # ours added


def test_init_write_flag_emits_mcp_json(tmp_path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path), "--write"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".mcp.json").exists()
    assert ".mcp.json" in result.output
