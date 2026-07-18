import json
from datetime import datetime

from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def test_verify_clean_exit_zero(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "ok.py").write_text("import os\n\ndef f():\n    return os.getcwd()\n")
    r = runner.invoke(app, ["verify", "ok.py", "--root", str(tmp_path)])
    assert r.exit_code == 0
    assert "PASS" in r.stdout


def test_verify_fails_exit_one(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    store = Store(TorsorPaths(tmp_path), clock=lambda: datetime(2026, 7, 18, 12, 0, 0))
    ops.record_decision(
        store, title="No requests in domain", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "domain/*.py", "severity": "error"}],
    )
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain" / "x.py").write_text("import requests\n")
    r = runner.invoke(app, ["verify", "domain/x.py", "--root", str(tmp_path)])
    assert r.exit_code == 1
    assert "FAIL" in r.stdout


def test_verify_json_verdict_shape(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "ok.py").write_text("import os\n")
    r = runner.invoke(app, ["verify", "ok.py", "--root", str(tmp_path), "--json"])
    verdict = json.loads(r.stdout)
    assert set(verdict) == {"ok", "exit_code", "checks", "summary"}
    assert verdict["ok"] is True
    assert r.exit_code == 0
