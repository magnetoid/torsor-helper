from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.models import Frontmatter
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 7, 18, 12, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def _forbid_requests(store):
    ops.record_decision(
        store, title="No requests in domain", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "domain/*.py", "severity": "error"}],
    )


def test_clean_change_set_passes(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "ok.py").write_text("import os\n\ndef f():\n    return os.getcwd()\n")
    v = ops.verify(store, TorsorConfig(), ["ok.py"])
    assert v["ok"] is True
    assert v["exit_code"] == 0
    assert {c["name"] for c in v["checks"]} == {"guard", "deps", "staleness"}


def test_fails_on_forbidden_import_with_adr_reason(tmp_path):
    store = _store(tmp_path)
    _forbid_requests(store)
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain" / "x.py").write_text("import requests\n")
    v = ops.verify(store, TorsorConfig(), ["domain/x.py"])
    guard = next(c for c in v["checks"] if c["name"] == "guard")
    assert guard["ok"] is False
    assert v["ok"] is False and v["exit_code"] == 1
    assert any("No requests" in r or "requests" in r for r in guard["reasons"])  # cites the ADR


def test_baseline_grandfathered_drift_does_not_fail(tmp_path):
    store = _store(tmp_path)
    _forbid_requests(store)
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain" / "x.py").write_text("import requests\n")
    ops.guard_run(store, TorsorConfig(), ["domain/x.py"], update_baseline=True)  # grandfather it
    v = ops.verify(store, TorsorConfig(), ["domain/x.py"])
    assert next(c for c in v["checks"] if c["name"] == "guard")["ok"] is True


def test_fails_on_unknown_import(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "m.py").write_text("import totallynotarealpkg_xyz\n")
    v = ops.verify(store, TorsorConfig(), ["m.py"])
    assert next(c for c in v["checks"] if c["name"] == "deps")["ok"] is False
    assert v["ok"] is False


def test_fails_on_dangling_link(tmp_path):
    store = _store(tmp_path)
    store.write_note(store.paths.memory_dir / "n.md",
                     Frontmatter(type="observation", tags=["memory"]), "n", "See [[gone]].")
    v = ops.verify(store, TorsorConfig(), [])
    assert next(c for c in v["checks"] if c["name"] == "staleness")["ok"] is False


def test_tests_skip_when_no_command(tmp_path):
    store = _store(tmp_path)
    v = ops.verify(store, TorsorConfig(), [], run_tests=True)
    tests = next(c for c in v["checks"] if c["name"] == "tests")
    assert tests["status"] == "skip"
    assert v["ok"] is True  # a skipped test check never fails the gate


def test_tests_fail_on_failing_recorded_command(tmp_path):
    store = _store(tmp_path)
    ops.record_command(store, "test", "false", "always fails")
    v = ops.verify(store, TorsorConfig(), [], run_tests=True)
    assert next(c for c in v["checks"] if c["name"] == "tests")["ok"] is False
    assert v["ok"] is False
