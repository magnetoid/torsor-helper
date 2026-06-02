from datetime import datetime

from torsor_helper import baseline
from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.models import Violation
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _v(file, line=1, kind="forbid_import", target="requests"):
    return Violation(rule_kind=kind, target=target, file=file, line=line, message="m", source="s")


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "baseline.json"
    baseline.save(p, [_v("a.py", 1), _v("a.py", 2), _v("b.py")])
    bl = baseline.load(p)
    assert bl[("a.py", "forbid_import", "requests")] == 2
    assert bl[("b.py", "forbid_import", "requests")] == 1


def test_load_missing_or_corrupt_returns_empty(tmp_path):
    assert baseline.load(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("not json{")
    assert baseline.load(bad) == {}


def test_new_violations_only_counts_excess(tmp_path):
    p = tmp_path / "baseline.json"
    baseline.save(p, [_v("a.py", 1)])  # baseline: a.py has 1
    bl = baseline.load(p)
    # same tuple now has 2 → exactly 1 is new
    assert len(baseline.new_violations([_v("a.py", 1), _v("a.py", 5)], bl)) == 1
    # a brand-new file/tuple → all new
    assert len(baseline.new_violations([_v("c.py")], bl)) == 1
    # at/below baseline → none new
    assert baseline.new_violations([_v("a.py", 1)], bl) == []


def test_ops_new_drift_uses_baseline(tmp_path):
    runner_store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    runner_store.scaffold()
    ops.record_decision(
        runner_store, title="No requests", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "domain/*.py"}],
    )
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain" / "svc.py").write_text("import requests\n")
    cfg = TorsorConfig()
    # before baselining: it's new drift
    assert len(ops.new_drift(runner_store, cfg, ["domain/svc.py"])) == 1
    # baseline it
    baseline.save(runner_store.paths.baseline_file, ops.check_drift(runner_store, cfg, ["domain/svc.py"]))
    # now grandfathered → no new drift
    assert ops.new_drift(runner_store, cfg, ["domain/svc.py"]) == []
