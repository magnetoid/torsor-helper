import anyio
from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.server import build_server

runner = CliRunner()


def test_consolidate_cli_reports_counts(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["consolidate", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "insight" in result.output.lower()


def test_consolidate_requires_init(tmp_path):
    result = runner.invoke(app, ["consolidate", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "not initialized" in result.output.lower()


def test_server_registers_consolidate_tool(tmp_path):
    server = build_server(tmp_path)
    names = {t.name for t in anyio.run(server.list_tools)}
    assert "consolidate" in names
