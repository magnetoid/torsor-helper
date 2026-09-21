"""A `forbid_cycle` rule catches what no per-file rule can see.

Every other rule kind reads one file's source. A cycle is a property of the
whole import graph, so it needed a second evaluation path — one that runs once
per guard call, over the symbol map, and degrades to a no-op when no map
exists (the same rule as everywhere else: no index, reduced service, never an
error).
"""
from __future__ import annotations

from torsor_helper import guard, operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def _project(tmp_path, *, cyclic: bool):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("from pkg.b import beta\n\ndef alpha():\n    return beta()\n")
    if cyclic:
        (pkg / "b.py").write_text("from pkg.a import alpha\n\ndef beta():\n    return alpha()\n")
    else:
        (pkg / "b.py").write_text("def beta():\n    return 2\n")
    ops.record_decision(
        store, title="No import cycles", context="c", decision="d",
        rules=[{"kind": "forbid_cycle", "target": "pkg", "scope": "pkg/**/*.py", "severity": "error"}],
    )
    return store


def test_a_cycle_is_reported(tmp_path):
    store = _project(tmp_path, cyclic=True)
    ops.map_repo(store, TorsorConfig())

    violations = guard.check_cycles(store, guard.load_rules(store))

    assert len(violations) == 1
    assert "pkg.a" in violations[0].message and "pkg.b" in violations[0].message
    assert violations[0].severity == "error"


def test_an_acyclic_graph_is_silent(tmp_path):
    store = _project(tmp_path, cyclic=False)
    ops.map_repo(store, TorsorConfig())

    assert guard.check_cycles(store, guard.load_rules(store)) == []


def test_it_is_a_no_op_without_a_map(tmp_path):
    store = _project(tmp_path, cyclic=True)
    assert guard.check_cycles(store, guard.load_rules(store)) == []


def test_only_modules_inside_the_rule_target_count(tmp_path):
    store = _project(tmp_path, cyclic=True)
    ops.map_repo(store, TorsorConfig())
    rules = [r for r in guard.load_rules(store) if r.kind == "forbid_cycle"]
    rules[0].target = "somewhere_else"

    assert guard.check_cycles(store, rules) == []


def test_guard_run_includes_cycles(tmp_path):
    store = _project(tmp_path, cyclic=True)
    ops.map_repo(store, TorsorConfig())

    result = ops.guard_run(store, TorsorConfig(), [], strict=True)

    assert any(v.rule_kind == "forbid_cycle" for v in result["violations"])
    assert result["failed"] is True


def test_a_cycle_can_be_baselined_like_any_other_violation(tmp_path):
    store = _project(tmp_path, cyclic=True)
    ops.map_repo(store, TorsorConfig())
    ops.guard_run(store, TorsorConfig(), [], update_baseline=True)

    result = ops.guard_run(store, TorsorConfig(), [], strict=True)

    assert result["new"] == []
    assert result["failed"] is False
