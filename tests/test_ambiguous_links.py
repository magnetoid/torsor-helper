"""A wikilink that could mean two notes should say so.

`[[overview]]` resolves to the first matching path in sorted order — stable,
deterministic, and silently arbitrary when two tiers both hold an `overview.md`.
The resolution stays as it is (changing which note wins would rewrite existing
links), but the ambiguity becomes visible.
"""
from __future__ import annotations

from torsor_helper import db
from torsor_helper.coach import staleness
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    return store


def _note(store, rel, body="body"):
    path = store.paths.base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntype: note\n---\n\n# {path.stem}\n\n{body}\n", encoding="utf-8")
    return path


def test_slug_index_reports_which_basenames_are_ambiguous(tmp_path):
    store = _store(tmp_path)
    a = _note(store, "memory/overview.md")
    b = _note(store, "map/overview.md")
    conn = db.connect(store.paths.index_db)
    try:
        for p in (a, b):
            db.upsert_note(conn, str(p), "h", 4, "note", None, p.stem, "", "active")
        idx = db.SlugIndex(conn)

        assert idx.is_ambiguous("overview")
        assert not idx.is_ambiguous("charter")
        assert idx.resolve("overview") in (str(a), str(b))   # still deterministic
    finally:
        conn.close()


def test_resolution_is_unchanged_for_an_unambiguous_slug(tmp_path):
    store = _store(tmp_path)
    only = _note(store, "memory/unique-note.md")
    conn = db.connect(store.paths.index_db)
    try:
        db.upsert_note(conn, str(only), "h", 4, "note", None, "unique-note", "", "active")
        assert db.SlugIndex(conn).resolve("unique-note") == str(only)
    finally:
        conn.close()


def test_coach_flags_a_link_whose_target_is_ambiguous(tmp_path):
    store = _store(tmp_path)
    _note(store, "memory/overview.md")
    _note(store, "active/overview.md")
    _note(store, "memory/src.md", "See [[overview]].")

    recs = staleness.check_ambiguous_links(store)

    assert len(recs) == 1
    assert recs[0].kind == "ambiguous_link"
    assert "overview" in recs[0].message
    assert recs[0].severity == "info"   # advisory; the link still works


def test_coach_says_nothing_when_the_target_is_unique(tmp_path):
    store = _store(tmp_path)
    _note(store, "memory/target.md")
    _note(store, "memory/src.md", "See [[target]].")

    assert staleness.check_ambiguous_links(store) == []


def test_a_path_shaped_link_is_never_ambiguous(tmp_path):
    # The whole point of writing [[memory/overview]] is to disambiguate.
    store = _store(tmp_path)
    _note(store, "memory/overview.md")
    _note(store, "active/overview.md")
    _note(store, "memory/src.md", "See [[memory/overview]].")

    assert staleness.check_ambiguous_links(store) == []
