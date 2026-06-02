from datetime import datetime

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
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


def test_supersedes_flips_old_adr_status(tmp_path):
    store = _store(tmp_path)
    ops.record_decision(store, title="First", context="c", decision="d")  # 0002-first
    new_path = ops.record_decision(store, title="Second", context="c", decision="d", supersedes="0002")
    assert new_path.endswith("0003-second.md")
    old = store.read_note(store.paths.decisions_dir / "0002-first.md")
    assert old.frontmatter.status == "superseded"
    assert getattr(old.frontmatter, "superseded_by") == "0003-second"
    new = store.read_note(store.paths.decisions_dir / "0003-second.md")
    assert getattr(new.frontmatter, "supersedes") == "0002-first"


def test_get_intent_excludes_superseded_decision(tmp_path):
    store = _store(tmp_path)
    ops.record_decision(store, title="Keepme", context="c", decision="d")          # 0002
    ops.record_decision(store, title="Replacement", context="c", decision="d", supersedes="0002")
    out = ops.get_intent(store, TorsorConfig())
    assert "Keepme" not in out          # superseded title hidden from intent
    assert "Replacement" in out


def test_recall_excludes_superseded_decision(tmp_path):
    store = _store(tmp_path)
    ops.record_decision(store, title="Old auth", context="we use basic auth ztoken", decision="decided ztoken")
    ops.record_decision(store, title="New auth", context="we use oauth now", decision="decided", supersedes="0002")
    res = ops.recall(store, TorsorConfig(), "ztoken")
    assert not any("0002-old-auth" in h.path for h in res.hits)
