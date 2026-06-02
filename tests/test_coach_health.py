from datetime import datetime

from torsor_helper.coach import health
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_thin_flags_untouched_seed_files(tmp_path):
    store = _store(tmp_path)
    kinds = {r.kind for r in health.check_thin(store)}
    keys = {r.key for r in health.check_thin(store)}
    assert kinds == {"thin"}
    assert {"thin:charter", "thin:system_patterns", "thin:tech_context"} <= keys


def test_thin_clears_when_filled(tmp_path):
    store = _store(tmp_path)
    store.paths.charter.write_text("---\ntype: charter\n---\n\n# Charter\n\nReal content here.\n")
    keys = {r.key for r in health.check_thin(store)}
    assert "thin:charter" not in keys


def test_stale_flags_untouched_active_context(tmp_path):
    store = _store(tmp_path)
    recs = health.check_stale(store)
    assert any(r.kind == "stale" and r.key == "stale:active" for r in recs)


def test_unruled_flags_decisions_without_rules(tmp_path):
    store = _store(tmp_path)
    (store.paths.decisions_dir / "0002-x.md").write_text("---\ntype: decision\n---\n\n# ADR 0002: x\n\nb\n")
    recs = health.check_unruled(store)
    assert any(r.kind == "unruled" for r in recs)


def test_unruled_clears_when_a_rule_exists(tmp_path):
    store = _store(tmp_path)
    (store.paths.decisions_dir / "0002-x.md").write_text(
        "---\ntype: decision\nrules:\n  - kind: forbid_import\n    target: requests\n---\n\n# ADR 0002: x\n\nb\n"
    )
    assert health.check_unruled(store) == []


def test_uncharted_flags_unmapped_source(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "app.py").write_text("def run():\n    return 1\n")
    recs = health.check_uncharted(store, modules_in_map=set())
    assert any(r.kind == "uncharted" for r in recs)
    assert health.check_uncharted(store, modules_in_map={"app.py"}) == []
