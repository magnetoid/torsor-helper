from datetime import datetime

from torsor_helper import db
from torsor_helper.embeddings import HashingEmbedder
from torsor_helper.indexer import reindex
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _setup(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    conn = db.connect(tmp_path / "idx.db")
    return store, conn


def test_body_column_is_breadcrumb_free(tmp_path):
    """The FTS body (the snippet source) must stay byte-identical to the note body."""
    store, conn = _setup(tmp_path)
    store.append_journal("xyzzy unique content", kind="learning", links=[])
    reindex(store, conn, HashingEmbedder(dim=64))
    jpath = str(store.paths.journal_file("2026-06-01"))
    assert db.body_of(conn, jpath) == store.read_note(store.paths.journal_file("2026-06-01")).body
    # the charter too — no breadcrumb leaked into the snippet source
    cpath = str(store.paths.charter)
    assert db.body_of(conn, cpath) == store.read_note(store.paths.charter).body


def test_breadcrumb_lands_in_fts_title(tmp_path):
    store, conn = _setup(tmp_path)
    store.append_journal("xyzzy unique content", kind="learning", links=[])
    reindex(store, conn, HashingEmbedder(dim=64))
    jpath = str(store.paths.journal_file("2026-06-01"))
    title = conn.execute("SELECT title FROM fts WHERE path=?", (jpath,)).fetchone()["title"]
    # tier name (episodic) is the situating term — present in neither the body nor the H1 title
    assert "episodic" in title.lower()


def test_breadcrumb_term_is_retrievable(tmp_path):
    """A query for the situating tier term retrieves the note even though the term
    appears in neither its body nor its H1 title — the whole point of the breadcrumb."""
    store, conn = _setup(tmp_path)
    store.append_journal("xyzzy unique content", kind="learning", links=[])
    reindex(store, conn, HashingEmbedder(dim=64))
    jpath = str(store.paths.journal_file("2026-06-01"))
    hits = [p for p, _ in db.fts_search(conn, "episodic", 50)]
    assert jpath in hits
