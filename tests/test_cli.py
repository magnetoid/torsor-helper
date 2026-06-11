from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.paths import TorsorPaths

runner = CliRunner()


def test_init_scaffolds_and_prints_client_snippet(tmp_path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path), "--client", "cursor"])
    assert result.exit_code == 0, result.output
    paths = TorsorPaths(tmp_path)
    assert paths.charter.exists()
    assert paths.config_file.exists()
    assert "mcpServers" in result.output  # cursor JSON snippet printed


def test_doctor_reports_ok_after_init(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_doctor_flags_missing_project(tmp_path):
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "not initialized" in result.output.lower()


def test_init_rejects_unknown_client_without_scaffolding(tmp_path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path), "--client", "bogus"])
    assert result.exit_code == 1
    # must fail BEFORE creating any .torsor/ side effects
    assert not TorsorPaths(tmp_path).base.exists()


def test_doctor_reports_malformed_config(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    TorsorPaths(tmp_path).config_file.write_text("this is = not valid toml ===")
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "malformed" in result.output.lower()


def test_end_to_end_remember_then_bootstrap(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    from datetime import datetime

    from torsor_helper import operations as ops
    from torsor_helper.config import load_config
    from torsor_helper.store import Store

    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=lambda: datetime(2026, 6, 1, 9, 30, 0))
    ops.remember(store, "Picked FastMCP", kind="decision", links=[])
    out = ops.bootstrap_session(store, load_config(paths))
    assert "Picked FastMCP" in out


def test_mcp_http_warns_on_non_loopback_host(tmp_path, monkeypatch):
    import torsor_helper.server as server_mod

    monkeypatch.setattr(server_mod, "run", lambda *a, **k: None)
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["mcp", "--root", str(tmp_path), "--http", "--host", "0.0.0.0"])
    assert result.exit_code == 0, result.output
    assert "no authentication" in result.output


def test_mcp_http_loopback_does_not_warn(tmp_path, monkeypatch):
    import torsor_helper.server as server_mod

    monkeypatch.setattr(server_mod, "run", lambda *a, **k: None)
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["mcp", "--root", str(tmp_path), "--http"])
    assert "no authentication" not in result.output


def test_rules_prints_digest_and_writes_managed_block(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["rules", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Non-negotiable principles" in result.output

    target = tmp_path / "AGENTS.md"
    result = runner.invoke(app, ["rules", "--root", str(tmp_path), "--write", str(target)])
    assert result.exit_code == 0, result.output
    assert target.exists() and "torsor:rules" in target.read_text()
