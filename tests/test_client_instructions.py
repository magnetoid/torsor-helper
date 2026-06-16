from typer.testing import CliRunner

from torsor_helper import clients
from torsor_helper.cli import app

runner = CliRunner()


def test_instructions_file_defaults_and_overrides():
    assert clients.instructions_file("claude-code") == "CLAUDE.md"
    assert clients.instructions_file("gemini") == "GEMINI.md"
    assert clients.instructions_file("cursor") == "AGENTS.md"   # cross-tool default
    assert clients.instructions_file("unknown") == "AGENTS.md"


def test_models_client_writes_conventional_file(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    runner.invoke(app, ["models", "--root", str(tmp_path), "--cheap", "ha", "--smart", "op"])
    r = runner.invoke(app, ["models", "--root", str(tmp_path), "--client", "claude-code"])
    assert r.exit_code == 0, r.output
    assert "Model routing" in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")


def test_rules_and_primer_client_target(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    # cursor → AGENTS.md (cross-tool default)
    r = runner.invoke(app, ["primer", "--root", str(tmp_path), "--client", "cursor"])
    assert r.exit_code == 0
    assert (tmp_path / "AGENTS.md").exists()
    rr = runner.invoke(app, ["rules", "--root", str(tmp_path), "--client", "gemini"])
    assert rr.exit_code == 0
    assert (tmp_path / "GEMINI.md").exists()


def test_bad_client_errors(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    r = runner.invoke(app, ["models", "--root", str(tmp_path), "--client", "nope"])
    assert r.exit_code == 1
    assert "Unknown client" in r.output
