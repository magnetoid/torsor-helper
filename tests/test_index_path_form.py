"""Note paths in the index are POSIX-separated, whatever the OS wrote them.

`SlugIndex`, `_breadcrumb` and the wikilink resolver all split a stored path on
"/". On Windows `str(Path(...))` yields backslashes, so every one of those
splits saw a single segment: no wikilink edge ever resolved, and the breadcrumb
that situates a note for retrieval collapsed to its filename.

There is no Windows CI here, so these test the property directly rather than
the platform.
"""
from __future__ import annotations

from torsor_helper import db
from torsor_helper.indexer import _breadcrumb, reindex
from torsor_helper.models import Note, Tier
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    return store


def test_stored_note_paths_use_forward_slashes(tmp_path):
    store = _store(tmp_path)
    (store.paths.memory_dir / "deep.md").write_text(
        "---\ntype: note\n---\n\n# Deep\n\nbody\n", encoding="utf-8"
    )
    conn = db.connect(store.paths.index_db)
    try:
        from torsor_helper.embeddings import HashingEmbedder

        reindex(store, conn, HashingEmbedder(64))
        paths = [r["path"] for r in conn.execute("SELECT path FROM notes")]
        assert paths
        assert not any("\\" in p for p in paths)
    finally:
        conn.close()


def test_slug_resolution_works_on_a_windows_shaped_path(tmp_path):
    """The failure this guards: a backslash path has no "/" to split on, so the
    basename lookup never matched and every edge resolved to NULL."""
    conn = db.connect(tmp_path / "i.db")
    try:
        windows_style = r"C:\proj\.torsor\memory\target.md"
        db.upsert_note(conn, windows_style, "h", 4, "note", None, "Target", "", "active")
        idx = db.SlugIndex(conn)
        assert idx.resolve("target") == windows_style
    finally:
        conn.close()


def test_the_breadcrumb_keeps_its_directory_segments(tmp_path):
    note = Note(
        path=tmp_path / ".torsor" / "memory" / "insights" / "thing.md",
        tier=Tier.EPISODIC, title="Thing", frontmatter={"type": "note"},
        body="b", content_hash="h",
    )
    crumb = _breadcrumb(note)
    assert "insights" in crumb and "memory" in crumb
