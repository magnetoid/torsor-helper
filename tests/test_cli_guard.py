from datetime import datetime

from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def _seed(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    store = Store(TorsorPaths(tmp_path), clock=lambda: datetime(2026, 6, 2, 9, 0, 0))
    ops.record_decision(
        store, title="No requests in domain", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "domain/*.py"}],
    )
    (tmp_path / "domain").mkdir()


def test_guard_reports_violation_for_explicit_file(tmp_path):
    _seed(tmp_path)
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    result = runner.invoke(app, ["guard", "--root", str(tmp_path), "domain/svc.py"])
    assert result.exit_code == 0
    assert "violation" in result.output.lower()


def test_guard_strict_exits_nonzero_on_violation(tmp_path):
    _seed(tmp_path)
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    result = runner.invoke(app, ["guard", "--root", str(tmp_path), "--strict", "domain/svc.py"])
    assert result.exit_code == 1


def test_guard_clean_reports_no_drift(tmp_path):
    _seed(tmp_path)
    (tmp_path / "domain" / "ok.py").write_text("import os\n")
    result = runner.invoke(app, ["guard", "--root", str(tmp_path), "domain/ok.py"])
    assert result.exit_code == 0
    assert "no drift" in result.output.lower()
