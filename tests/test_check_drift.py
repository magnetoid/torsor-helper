from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _project_with_rule(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    ops.record_decision(
        store, title="No requests in domain", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "domain/*.py"}],
    )
    return store


def test_check_drift_flags_violation_with_explicit_files(tmp_path):
    store = _project_with_rule(tmp_path)
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    violations = ops.check_drift(store, TorsorConfig(), files=["domain/svc.py"])
    assert len(violations) == 1
    assert violations[0].file == "domain/svc.py"
    assert "No requests in domain" in violations[0].source


def test_check_drift_clean_when_no_violation(tmp_path):
    store = _project_with_rule(tmp_path)
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain" / "ok.py").write_text("import os\n")
    assert ops.check_drift(store, TorsorConfig(), files=["domain/ok.py"]) == []
