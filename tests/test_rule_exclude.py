"""A rule needs a way to say "everywhere except here".

ADR 0002 forbids importing the CLI entry point, which is right for every core
module and wrong for `__main__.py`, whose entire job is to be an entry point.
Without an exception mechanism the choice is a rule that lies or a file that
cannot exist — and every comparable tool (import-linter, ArchUnit,
dependency-cruiser) has one.
"""
from __future__ import annotations

from torsor_helper import guard, operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.models import Rule
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    return store


def test_an_excluded_file_is_not_checked(tmp_path):
    store = _store(tmp_path)
    ops.record_decision(
        store, title="No requests", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "**/*.py",
                "exclude": "**/legacy.py", "severity": "error"}],
    )
    (tmp_path / "fresh.py").write_text("import requests\n")
    (tmp_path / "legacy.py").write_text("import requests\n")

    files = [v.file for v in guard.check_drift(store, ["fresh.py", "legacy.py"])]

    assert files == ["fresh.py"]


def test_no_exclude_means_no_exception(tmp_path):
    store = _store(tmp_path)
    ops.record_decision(
        store, title="No requests", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "**/*.py", "severity": "error"}],
    )
    (tmp_path / "a.py").write_text("import requests\n")

    assert len(guard.check_drift(store, ["a.py"])) == 1


def test_exclude_uses_the_same_path_aware_matching_as_scope():
    rule = Rule(kind="forbid_import", target="x", scope="src/**/*.py",
                exclude="src/pkg/*.py", source="t")
    assert guard.rule_applies("src/pkg/a.py", rule) is False      # direct child: excluded
    assert guard.rule_applies("src/pkg/sub/a.py", rule) is True   # deeper: * does not cross /
    assert guard.rule_applies("src/other/a.py", rule) is True


def test_the_cycle_rule_honours_exclude_too(tmp_path):
    store = _store(tmp_path)
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("from pkg.b import beta\n\ndef alpha():\n    return beta()\n")
    (pkg / "b.py").write_text("from pkg.a import alpha\n\ndef beta():\n    return alpha()\n")
    ops.map_repo(store, TorsorConfig())
    rule = Rule(kind="forbid_cycle", target="pkg", scope="pkg/**/*.py",
                exclude="pkg/b.py", source="t")

    assert guard.check_cycles(store, [rule]) == []


def test_this_repos_entry_point_is_allowed_to_import_the_cli():
    """The violation that motivated this: `python -m torsor_helper` needs a
    __main__.py, and a module whose whole purpose is to be an entry point is
    not the "nothing" ADR 0002 means."""
    from pathlib import Path

    store = Store(TorsorPaths(Path(__file__).resolve().parents[1]))
    violations = guard.check_drift(store, ["src/torsor_helper/__main__.py"])

    assert violations == []
