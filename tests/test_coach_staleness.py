"""Staleness detectors: memory that contradicts current code. Deterministic and
high-precision by design — false positives here become nagging, so the detectors
only fire on unambiguous signals (a link/path that resolves to nothing)."""
from datetime import datetime

from torsor_helper.coach import staleness
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


def test_dangling_link_flagged_then_cleared(tmp_path):
    store = _store(tmp_path)
    _note(store, "alpha", "See [[beta-note]] for details.")
    recs = staleness.check_dangling_links(store)
    assert any(r.kind == "dangling_link" and "beta-note" in r.message for r in recs)

    # Create the target note → the finding clears.
    _note(store, "beta-note", "here I am")
    recs = staleness.check_dangling_links(store)
    assert not any(r.kind == "dangling_link" and "beta-note" in r.message for r in recs)


def test_resolved_wikilink_not_flagged(tmp_path):
    store = _store(tmp_path)
    _note(store, "beta-note", "target")
    _note(store, "alpha", "See [[beta-note]].")
    assert not any(r.kind == "dangling_link" for r in staleness.check_dangling_links(store))


def test_missing_path_ref_flagged_then_cleared(tmp_path):
    store = _store(tmp_path)
    _note(store, "arch", "The logic lives in `src/app/gone.py` today.")
    recs = staleness.check_path_refs(store)
    assert any(r.kind == "stale_path" and "src/app/gone.py" in r.message for r in recs)

    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "src" / "app" / "gone.py").write_text("x = 1\n")
    recs = staleness.check_path_refs(store)
    assert not any(r.kind == "stale_path" for r in recs)


def test_existing_path_ref_not_flagged(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "real.py").write_text("x = 1\n")
    _note(store, "arch", "See `pkg/real.py`.")
    assert not any(r.kind == "stale_path" for r in staleness.check_path_refs(store))


def test_bare_filename_without_slash_is_ignored(tmp_path):
    # A bare `operations.py:42` mention is too ambiguous to resolve — never flag it.
    store = _store(tmp_path)
    _note(store, "note", "fixed in operations.py at line 42")
    assert not any(r.kind == "stale_path" for r in staleness.check_path_refs(store))


def test_urls_and_fenced_code_are_ignored(tmp_path):
    store = _store(tmp_path)
    _note(store, "note", "docs at https://example.com/pkg/thing.py\n\n```\nimport foo/bar.py\n```\n")
    assert not any(r.kind == "stale_path" for r in staleness.check_path_refs(store))


def test_findings_have_stable_keys(tmp_path):
    store = _store(tmp_path)
    _note(store, "alpha", "See [[gone]] and `src/x/dead.py`.")
    keys = [r.key for r in staleness.check_dangling_links(store) + staleness.check_path_refs(store)]
    assert len(keys) == len(set(keys))  # stable + unique for dismissal/decay
    assert all(":" in k for k in keys)
