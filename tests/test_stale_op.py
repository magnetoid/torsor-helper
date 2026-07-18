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


def _note(store, name, body):
    store.write_note(store.paths.memory_dir / f"{name}.md",
                     Frontmatter(type="observation", tags=["memory"]), name, body)
    return store.paths.memory_dir / f"{name}.md"


def test_check_staleness_counts_by_kind(tmp_path):
    store = _store(tmp_path)
    _note(store, "n", "See [[gone]] and `src/x/dead.py`.")
    result = ops.check_staleness(store, TorsorConfig())
    assert result["counts"].get("dangling_link") == 1
    assert result["counts"].get("stale_path") == 1


def test_mark_sets_status_and_preserves_body(tmp_path):
    store = _store(tmp_path)
    path = _note(store, "n", "important body text\n\nSee [[gone]].")
    result = ops.check_staleness(store, TorsorConfig(), mark=True)
    assert result["marked"]  # note path recorded
    note = store.read_note(path)
    assert note.frontmatter.status == "stale"
    assert "important body text" in note.body  # body untouched


def test_unmark_restores_active(tmp_path):
    store = _store(tmp_path)
    path = _note(store, "n", "See [[gone]].")
    ops.check_staleness(store, TorsorConfig(), mark=True)
    assert store.read_note(path).frontmatter.status == "stale"
    ops.check_staleness(store, TorsorConfig(), unmark=True)
    assert store.read_note(path).frontmatter.status == "active"


def test_mark_is_idempotent(tmp_path):
    store = _store(tmp_path)
    _note(store, "n", "See [[gone]].")
    ops.check_staleness(store, TorsorConfig(), mark=True)
    second = ops.check_staleness(store, TorsorConfig(), mark=True)
    assert second["marked"] == []  # already stale → no rewrite


def test_clean_project_has_no_findings(tmp_path):
    store = _store(tmp_path)
    _note(store, "target", "here")
    _note(store, "n", "See [[target]].")
    result = ops.check_staleness(store, TorsorConfig())
    assert result["findings"] == []
