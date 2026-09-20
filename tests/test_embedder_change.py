"""A transiently missing embedder must not rewrite the whole index.

`get_embedder` falls back to the hashing embedder whenever fastembed raises —
including a first-run model download with no network. Treating that as "the
embedder changed" re-embedded every note with hashing, and re-embedded them all
back the moment fastembed worked again. On an offline-first tool that flip can
happen on any call.
"""
from __future__ import annotations

from torsor_helper import db
from torsor_helper.embeddings import HashingEmbedder
from torsor_helper.indexer import reindex
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


class _FakeFastEmbed(HashingEmbedder):
    """Same vectors, different identity — so only the identity check reacts."""

    name = "fastembed"
    model = "BAAI/bge-small-en-v1.5"


def _store(tmp_path, notes=5):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    for i in range(notes):
        (store.paths.memory_dir / f"n{i}.md").write_text(
            f"---\ntype: note\n---\n\n# N{i}\n\nwidget content {i}\n", encoding="utf-8"
        )
    return store


def test_a_different_embedder_does_not_re_embed_the_corpus(tmp_path):
    store = _store(tmp_path)
    conn = db.connect(store.paths.index_db)
    try:
        first = reindex(store, conn, _FakeFastEmbed(384))
        assert first["indexed"] >= 5

        # fastembed is unavailable this run; get_embedder hands back hashing.
        second = reindex(store, conn, HashingEmbedder(384))

        assert second["indexed"] == 0, "re-embedded the whole corpus over a transient fallback"
        assert db.meta_get(conn, "embedder").startswith("fastembed"), "stored identity was overwritten"
    finally:
        conn.close()


def test_the_good_vectors_are_left_in_place(tmp_path):
    store = _store(tmp_path)
    conn = db.connect(store.paths.index_db)
    try:
        reindex(store, conn, _FakeFastEmbed(384))
        before = db.get_vectors(conn, [str(p) for p in store.iter_note_paths()])
        reindex(store, conn, HashingEmbedder(384))
        after = db.get_vectors(conn, [str(p) for p in store.iter_note_paths()])
        assert set(before) == set(after)
    finally:
        conn.close()


def test_new_notes_still_get_indexed_for_keyword_search(tmp_path):
    """The FTS side must keep working — only embedding is paused."""
    store = _store(tmp_path)
    conn = db.connect(store.paths.index_db)
    try:
        reindex(store, conn, _FakeFastEmbed(384))
        (store.paths.memory_dir / "fresh.md").write_text(
            "---\ntype: note\n---\n\n# Fresh\n\nwidget newest\n", encoding="utf-8"
        )
        reindex(store, conn, HashingEmbedder(384))
        assert db.fts_search(conn, "newest", 5), "the new note never reached the text index"
    finally:
        conn.close()


def test_returning_to_the_original_embedder_is_also_a_no_op(tmp_path):
    store = _store(tmp_path)
    conn = db.connect(store.paths.index_db)
    try:
        reindex(store, conn, _FakeFastEmbed(384))
        reindex(store, conn, HashingEmbedder(384))
        back = reindex(store, conn, _FakeFastEmbed(384))
        assert back["indexed"] == 0
    finally:
        conn.close()
