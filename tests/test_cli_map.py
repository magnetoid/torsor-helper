from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.paths import TorsorPaths

runner = CliRunner()


def test_map_reports_counts_and_writes_overview(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "app.py").write_text("def run():\n    return 1\n")
    result = runner.invoke(app, ["map", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "mapped" in result.output.lower()
    assert TorsorPaths(tmp_path).map_overview.exists()


def test_map_requires_init(tmp_path):
    result = runner.invoke(app, ["map", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "not initialized" in result.output.lower()
