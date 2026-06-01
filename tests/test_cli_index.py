from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.paths import TorsorPaths

runner = CliRunner()


def test_index_builds_db_and_reports_counts(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["index", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "indexed" in result.output.lower()
    assert TorsorPaths(tmp_path).index_db.exists()


def test_index_full_rebuild_flag(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    runner.invoke(app, ["index", "--root", str(tmp_path)])
    result = runner.invoke(app, ["index", "--root", str(tmp_path), "--full"])
    assert result.exit_code == 0
    assert "indexed" in result.output.lower()
