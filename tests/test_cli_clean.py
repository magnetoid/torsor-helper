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

    result = runner.invoke(app, ["clean", "--root", str(tmp_path), "--apply", "--deep", "--yes"])

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


def test_expiring_journals_takes_its_own_flag(tmp_path):
    # A project initialized by an older torsor has the old default written into
    # its torsor.toml. `clean --apply` must not treat that as consent.
    from datetime import date, timedelta

    runner.invoke(app, ["init", "--root", str(tmp_path)])
    config_file = tmp_path / ".torsor" / "torsor.toml"
    config_file.write_text(config_file.read_text(encoding="utf-8").replace(
        "journal_retention_days = 0", "journal_retention_days = 90"), encoding="utf-8")
    assert "journal_retention_days = 90" in config_file.read_text(encoding="utf-8")
    stamp = (date.today() - timedelta(days=400)).isoformat()
    journal = tmp_path / ".torsor" / "memory" / "journal" / f"{stamp}.md"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(f"---\ntype: journal\n---\n\n# Journal {stamp}\n\n## 09:00 · learning\nkeep me\n",
                       encoding="utf-8")

    kept = runner.invoke(app, ["clean", "--apply", "--root", str(tmp_path)])
    assert kept.exit_code == 0, kept.output
    assert journal.exists()
    assert "--expire-journals" in kept.output

    gone = runner.invoke(app, ["clean", "--apply", "--expire-journals", "--root", str(tmp_path)])
    assert gone.exit_code == 0, gone.output
    assert not journal.exists()


def test_the_mcp_clean_tool_cannot_expire_journals(tmp_path):
    # Deleting the only copy of what was remembered is an operator decision,
    # like the hook installers (ADR 0009): the agent-facing tool has no way to ask.
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    tools = {t.name: t for t in anyio.run(build_server(tmp_path).list_tools)}
    assert set(tools["clean"].inputSchema.get("properties") or {}) == {"apply", "deep"}
