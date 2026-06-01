from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.guard import load_rules
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_record_decision_numbers_and_writes_adr(tmp_path):
    store = _store(tmp_path)
    path = ops.record_decision(
        store, title="Use SQLite for the index",
        context="We need local-first storage.", decision="Adopt SQLite.",
        consequences="No server to run.",
    )
    assert path.endswith("0002-use-sqlite-for-the-index.md")
    text = (store.paths.decisions_dir / "0002-use-sqlite-for-the-index.md").read_text()
    assert "# ADR 0002: Use SQLite for the index" in text
    assert "## Decision" in text and "Adopt SQLite." in text


def test_record_decision_rules_become_loadable(tmp_path):
    store = _store(tmp_path)
    ops.record_decision(
        store, title="No requests in domain", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "domain/*.py"}],
    )
    rules = load_rules(store)
    assert any(r.target == "requests" and r.kind == "forbid_import" for r in rules)
