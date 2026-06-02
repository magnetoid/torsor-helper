from typer.testing import CliRunner

from torsor_helper.cli import app

runner = CliRunner()


def test_coach_reports_hygiene_on_fresh_project(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["coach", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "seed template" in result.output.lower()


def test_coach_dismiss_then_hidden(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    runner.invoke(app, ["coach", "--root", str(tmp_path), "--dismiss", "thin:charter"])
    result = runner.invoke(app, ["coach", "--root", str(tmp_path)])
    assert "thin:charter" not in result.output


def test_coach_requires_init(tmp_path):
    result = runner.invoke(app, ["coach", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "not initialized" in result.output.lower()
