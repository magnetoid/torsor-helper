import json
from datetime import datetime

from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def _seed(tmp_path, severity="warning"):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    store = Store(TorsorPaths(tmp_path), clock=lambda: datetime(2026, 6, 2, 9, 0, 0))
    ops.record_decision(
        store, title="No requests in domain", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "domain/*.py", "severity": severity}],
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


def test_guard_json_emits_machine_readable(tmp_path):
    _seed(tmp_path, severity="error")
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    result = runner.invoke(app, ["guard", "--root", str(tmp_path), "--json", "domain/svc.py"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert {"rule_id", "severity", "file", "line", "message", "source"} <= set(data[0])
    assert data[0]["severity"] == "error"
    assert data[0]["rule_id"] == "forbid_import:requests"


def test_guard_strict_severity_threshold_below_passes(tmp_path):
    _seed(tmp_path, severity="hint")  # a hint-level rule
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    result = runner.invoke(app, ["guard", "--root", str(tmp_path), "--strict", "--severity", "warning", "domain/svc.py"])
    assert result.exit_code == 0  # hint < warning threshold → no CI failure


def test_guard_strict_severity_threshold_met_fails(tmp_path):
    _seed(tmp_path, severity="error")
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    result = runner.invoke(app, ["guard", "--root", str(tmp_path), "--strict", "--severity", "warning", "domain/svc.py"])
    assert result.exit_code == 1  # error ≥ warning threshold → CI failure


def test_guard_json_strict_fails_on_new(tmp_path):
    _seed(tmp_path)
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    result = runner.invoke(app, ["guard", "--root", str(tmp_path), "--json", "--strict", "domain/svc.py"])
    assert result.exit_code == 1                      # new drift fails CI
    assert len(json.loads(result.output)) >= 1        # ...while still emitting JSON findings


def test_guard_json_strict_passes_when_baselined(tmp_path):
    _seed(tmp_path)
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    runner.invoke(app, ["guard", "--root", str(tmp_path), "--update-baseline", "domain/svc.py"])
    result = runner.invoke(app, ["guard", "--root", str(tmp_path), "--json", "--strict", "domain/svc.py"])
    assert result.exit_code == 0                       # grandfathered → CI passes
    assert len(json.loads(result.output)) == 1         # ...but the violation is still reported in JSON


def test_guard_baseline_grandfathers_then_fails_on_new(tmp_path):
    _seed(tmp_path)
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    # record the existing violation as the accepted baseline
    r1 = runner.invoke(app, ["guard", "--root", str(tmp_path), "--update-baseline", "domain/svc.py"])
    assert r1.exit_code == 0
    assert TorsorPaths(tmp_path).baseline_file.exists()
    # strict now passes — the pre-existing debt is grandfathered
    r2 = runner.invoke(app, ["guard", "--root", str(tmp_path), "--strict", "domain/svc.py"])
    assert r2.exit_code == 0
    assert "baselined" in r2.output.lower()
    # a NEW violation in another file fails strict
    (tmp_path / "domain" / "other.py").write_text("import requests\n")
    r3 = runner.invoke(app, ["guard", "--root", str(tmp_path), "--strict", "domain/svc.py", "domain/other.py"])
    assert r3.exit_code == 1
