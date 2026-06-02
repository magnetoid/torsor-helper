from datetime import datetime

from torsor_helper.coach import mining
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_parse_journal_entries_splits_by_kind():
    body = (
        "## 09:00 · learning\n\nprefer uv run over pip\n\nLinks: [[charter]]\n"
        "## 10:00 · decision\n\nchose SQLite\n"
    )
    entries = mining.parse_journal_entries(body)
    assert ("learning", "prefer uv run over pip") in entries
    assert ("decision", "chose SQLite") in entries
    assert all("Links:" not in c for _, c in entries)


def test_mine_insights_writes_per_kind_notes(tmp_path):
    store = _store(tmp_path)
    store.append_journal("prefer uv run over pip", kind="learning", links=[])
    store.append_journal("always TDD", kind="learning", links=[])
    store.append_journal("avoid global state", kind="rejection", links=[])
    written = mining.mine_insights(store)
    names = {p.name for p in written}
    assert "learning.md" in names and "rejection.md" in names
    learning_md = (store.paths.insights_dir / "learning.md").read_text()
    assert "prefer uv run over pip" in learning_md and "always TDD" in learning_md


def test_mine_insights_is_idempotent(tmp_path):
    store = _store(tmp_path)
    store.append_journal("only once", kind="learning", links=[])
    mining.mine_insights(store)
    mining.mine_insights(store)
    text = (store.paths.insights_dir / "learning.md").read_text()
    assert text.count("only once") == 1


def test_find_duplicate_entries(tmp_path):
    store = _store(tmp_path)
    store.append_journal("dup note", kind="observation", links=[])
    store.append_journal("dup note", kind="observation", links=[])
    store.append_journal("unique", kind="observation", links=[])
    dups = mining.find_duplicate_entries(store)
    assert ("dup note", 2) in dups
    assert all(c != "unique" for c, _ in dups)
