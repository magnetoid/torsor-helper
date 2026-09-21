"""The hashing fallback may reorder results. It may not create them.

Without fastembed, `get_embedder` returns a bag-of-words hashing embedder whose
384 md5 buckets give *every* query some similarity to *every* note. So a query
for something the project has never recorded came back with the charter and six
other notes, presented as matches — recall could never say "nothing here".

A real embedder introducing a hit with no lexical overlap is the whole point of
semantic search, so the rule is specific to the fallback: it ranks what the
lexical side already found a basis for, and adds nothing of its own.
"""
from __future__ import annotations

from torsor_helper import db, operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.embeddings import HashingEmbedder
from torsor_helper.paths import TorsorPaths
from torsor_helper.search import hybrid_search
from torsor_helper.store import Store


class _FakeSemantic(HashingEmbedder):
    """Identity of a real embedder, vectors of the fake one."""

    name = "fastembed"
    model = "BAAI/bge-small-en-v1.5"


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    for i in range(4):
        (store.paths.memory_dir / f"n{i}.md").write_text(
            f"---\ntype: note\n---\n\n# Note {i}\n\nwidget content {i}\n", encoding="utf-8"
        )
    return store


def test_a_query_with_no_lexical_match_returns_nothing(tmp_path):
    store = _store(tmp_path)
    config = TorsorConfig()
    ops.recall(store, config, "widget")          # build the index

    assert ops.recall(store, config, "qwrtzxcvb").hits == []


def test_a_query_that_does_match_is_unaffected(tmp_path):
    store = _store(tmp_path)
    config = TorsorConfig()

    hits = ops.recall(store, config, "widget").hits

    assert hits and all("Note" in h.title for h in hits if h.path)


def test_a_real_embedder_may_still_introduce_a_hit(tmp_path):
    """The restriction is on the fallback, not on semantic search."""
    store = _store(tmp_path)
    config = TorsorConfig()
    conn = db.connect(store.paths.index_db)
    try:
        from torsor_helper.indexer import reindex

        embedder = _FakeSemantic(384)
        reindex(store, conn, embedder)
        result = hybrid_search(conn, embedder, config, "qwrtzxcvb", limit=5)
        assert result.hits, "a real embedder's vector leg was suppressed"
    finally:
        conn.close()
