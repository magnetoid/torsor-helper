import anyio
from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.server import build_server

runner = CliRunner()


def _project_with_orphan(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "gone.py").write_text("def dropped():\n    return 2\n", encoding="utf-8")
    runner.invoke(app, ["map", "--root", str(tmp_path)])
    (tmp_path / "gone.py").unlink()
    return tmp_path / ".torsor" / "map" / "modules" / "gone.py.md"


def test_clean_is_a_dry_run_by_default(tmp_path):
    orphan = _project_with_orphan(tmp_path)

    result = runner.invoke(app, ["clean", "--root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "--apply" in result.output  # tells the user how to act on the plan
    assert orphan.exists()


def test_clean_apply_removes_the_orphan(tmp_path):
    orphan = _project_with_orphan(tmp_path)

    result = runner.invoke(app, ["clean", "--root", str(tmp_path), "--apply"])

    assert result.exit_code == 0, result.output
    assert not orphan.exists()


def test_clean_deep_drops_the_index(tmp_path):
    _project_with_orphan(tmp_path)

    result = runner.invoke(app, ["clean", "--root", str(tmp_path), "--apply", "--deep"])

    assert result.exit_code == 0, result.output
    assert not (tmp_path / ".torsor" / ".index").exists()
    assert (tmp_path / ".torsor" / "charter.md").exists()


def test_clean_requires_init(tmp_path):
    result = runner.invoke(app, ["clean", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "not initialized" in result.output.lower()


def test_server_registers_clean_tool(tmp_path):
    names = {t.name for t in anyio.run(build_server(tmp_path).list_tools)}
    assert "clean" in names
