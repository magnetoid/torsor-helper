"""Linking the two graphs torsor already keeps: notes and symbols.

`impact` has always answered "what code calls this symbol". The other half —
"what did we *decide* about it" — is the query this architecture uniquely
enables, and it did not ship.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from torsor_helper import db
from torsor_helper.config import TorsorConfig
from torsor_helper.models import Frontmatter
from torsor_helper.operations import graph as graph_ops
from torsor_helper.operations import memory as memory_ops
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


# ---- extraction ----

@pytest.mark.parametrize(
    "body,expected",
    [
        ("We call `norm_path` here.", ["norm_path"]),
        ("`map_repo()` writes notes.", ["map_repo"]),
        ("Use `ops.recall` instead.", ["ops.recall", "recall"]),
        ("Run `torsor map --force` first.", []),
        ("The `--json` flag.", []),
        ("Nothing in backticks at all.", []),
        ("`norm_path` and `norm_path` again.", ["norm_path"]),
    ],
)
def test_extract_symbol_mentions(body, expected):
    assert Store.extract_symbol_mentions(body) == expected


def test_fenced_code_is_not_a_mention():
    """A code sample is an illustration, not a claim about a symbol."""
    body = "Mentions `real_symbol`.\n\n```python\ndef decoy():\n    other_decoy()\n```\n"
    assert Store.extract_symbol_mentions(body) == ["real_symbol"]


def test_extraction_is_bounded_per_note():
    """One pathological note must not flood the table."""
    body = " ".join(f"`sym_{i}`" for i in range(500))
    assert len(Store.extract_symbol_mentions(body)) <= 200


# ---- indexing ----

def _indexed(store):
    from torsor_helper.embeddings import HashingEmbedder
    from torsor_helper.indexer import reindex

    conn = db.connect(store.paths.index_db)
    reindex(store, conn, HashingEmbedder(384))
    return conn


def test_reindex_records_mentions(tmp_path):
    store = _store(tmp_path)
    note = store.paths.decisions_dir / "0001-x.md"
    store.write_note(note, Frontmatter(type="decision"), "Use norm_path", "Always call `norm_path`.")
    conn = _indexed(store)
    try:
        assert note.as_posix() in db.notes_mentioning(conn, "norm_path")
    finally:
        conn.close()


def test_deleting_a_note_drops_its_mentions(tmp_path):
    store = _store(tmp_path)
    note = store.paths.decisions_dir / "0001-x.md"
    store.write_note(note, Frontmatter(type="decision"), "Use norm_path", "Always call `norm_path`.")
    conn = _indexed(store)
    try:
        note.unlink()
        from torsor_helper.embeddings import HashingEmbedder
        from torsor_helper.indexer import reindex

        reindex(store, conn, HashingEmbedder(384))
        assert db.notes_mentioning(conn, "norm_path") == []
    finally:
        conn.close()


def test_editing_a_note_replaces_its_mentions(tmp_path):
    store = _store(tmp_path)
    note = store.paths.decisions_dir / "0001-x.md"
    store.write_note(note, Frontmatter(type="decision"), "X", "We use `old_name`.")
    conn = _indexed(store)
    try:
        store.write_note(note, Frontmatter(type="decision"), "X", "We use `new_name`.")
        from torsor_helper.embeddings import HashingEmbedder
        from torsor_helper.indexer import reindex

        reindex(store, conn, HashingEmbedder(384))
        assert db.notes_mentioning(conn, "old_name") == []
        assert note.as_posix() in db.notes_mentioning(conn, "new_name")
    finally:
        conn.close()


def test_a_note_indexed_before_the_map_still_links(tmp_path):
    """The link is resolved at query time, not at index time.

    Filtering mentions against the symbols table while indexing would have made
    the feature depend on the order the two indexes were built in — and a note
    written before the first `torsor map` is never re-read, because reindex
    screens on (mtime, size)."""
    store = _store(tmp_path)
    note = store.paths.decisions_dir / "0001-x.md"
    store.write_note(note, Frontmatter(type="decision"), "X", "We call `target_fn`.")
    conn = _indexed(store)
    conn.close()

    (tmp_path / "mod.py").write_text("def target_fn():\n    return 1\n", encoding="utf-8")
    graph_ops.map_repo(store, TorsorConfig())

    result = graph_ops.impact(store, TorsorConfig(), "target_fn")
    assert [m["title"] for m in result["mentions"]] == ["X"]


# ---- impact: the killer query ----

def test_impact_reports_the_decisions_that_mention_the_symbol(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "mod.py").write_text("def target_fn():\n    return 1\n", encoding="utf-8")
    store.write_note(
        store.paths.decisions_dir / "0001-x.md",
        Frontmatter(type="decision"), "Never inline target_fn", "Call `target_fn`, never inline it.",
    )
    store.append_journal("learned that `target_fn` is slow", kind="learning", links=[])
    graph_ops.map_repo(store, TorsorConfig())

    result = graph_ops.impact(store, TorsorConfig(), "target_fn")
    titles = {m["title"] for m in result["mentions"]}
    assert "Never inline target_fn" in titles
    assert result["mentions_count"] == len(titles)


def test_impact_mentions_are_budgeted(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "mod.py").write_text("def target_fn():\n    return 1\n", encoding="utf-8")
    for i in range(12):
        store.write_note(
            store.paths.decisions_dir / f"{i:04d}-x.md",
            Frontmatter(type="decision"), f"Decision {i}", "About `target_fn`.",
        )
    graph_ops.map_repo(store, TorsorConfig())

    config = TorsorConfig()
    config.budgets.max_items = 5
    result = graph_ops.impact(store, config, "target_fn")
    assert len(result["mentions"]) == 5
    assert result["mentions_count"] == 12  # the true total is always reported


def test_impact_without_an_index_is_still_empty_not_broken(tmp_path):
    store = _store(tmp_path)
    result = graph_ops.impact(store, TorsorConfig(), "anything")
    assert result["mentions"] == [] and result["mentions_count"] == 0


def test_impact_finds_mentions_of_a_symbol_with_no_callers(tmp_path):
    """The two halves are independent: a symbol nothing calls can still be the
    one the team argued about."""
    store = _store(tmp_path)
    (tmp_path / "mod.py").write_text("def lonely():\n    return 1\n", encoding="utf-8")
    store.write_note(
        store.paths.decisions_dir / "0001-x.md",
        Frontmatter(type="decision"), "Keep lonely", "`lonely` stays for now.",
    )
    graph_ops.map_repo(store, TorsorConfig())

    result = graph_ops.impact(store, TorsorConfig(), "lonely")
    assert result["count"] == 0
    assert [m["title"] for m in result["mentions"]] == ["Keep lonely"]


# ---- recall: symbol= ----

def test_recall_can_be_restricted_to_a_symbol(tmp_path):
    store = _store(tmp_path)
    store.write_note(
        store.paths.decisions_dir / "0001-a.md",
        Frontmatter(type="decision"), "Caching policy", "Cache results of `target_fn`.",
    )
    store.write_note(
        store.paths.decisions_dir / "0002-b.md",
        Frontmatter(type="decision"), "Caching elsewhere", "Cache results of `other_fn`.",
    )
    config = TorsorConfig()
    memory_ops.recall(store, config, "cache")  # builds the index

    result = memory_ops.recall(store, config, "cache", symbol="target_fn")
    assert [h.title for h in result.hits] == ["Caching policy"]


def test_symbol_filter_works_without_an_index(tmp_path):
    """The keyword fallback applies the same filter itself — it has no SQL to
    push it into, which is how type_/kind were dropped there once before."""
    store = _store(tmp_path)
    store.write_note(
        store.paths.decisions_dir / "0001-a.md",
        Frontmatter(type="decision"), "Caching policy", "Cache results of `target_fn`.",
    )
    store.write_note(
        store.paths.decisions_dir / "0002-b.md",
        Frontmatter(type="decision"), "Caching elsewhere", "Cache results of `other_fn`.",
    )
    config = TorsorConfig()
    config.index.auto_index = False
    result = memory_ops.recall(store, config, "cache", symbol="target_fn")
    assert [h.title for h in result.hits] == ["Caching policy"]


# ---- get_intent ----

def test_get_intent_shows_what_was_recorded_about_the_topic(tmp_path):
    """Asserted on a *journal* note, not a decision: get_intent already lists
    every ADR title, so a decision would pass this test with no new code at all."""
    store = _store(tmp_path)
    (tmp_path / "mod.py").write_text("def target_fn():\n    return 1\n", encoding="utf-8")
    store.append_journal("`target_fn` is slower than it looks", kind="learning", links=[])
    store.append_journal("nothing to do with the topic", kind="learning", links=[])
    graph_ops.map_repo(store, TorsorConfig())

    text = memory_ops.get_intent(store, TorsorConfig(), topic="target_fn")
    assert "Journal 2026-06-01" in text


def test_get_intent_without_a_topic_has_no_mentions_section(tmp_path):
    store = _store(tmp_path)
    store.append_journal("`target_fn` is slow", kind="learning", links=[])
    text = memory_ops.get_intent(store, TorsorConfig())
    assert "mention" not in text.lower()


# ---- adapters ----

def test_cli_impact_renders_the_mentions(tmp_path):
    from typer.testing import CliRunner

    from torsor_helper.cli import app

    store = _store(tmp_path)
    (tmp_path / "mod.py").write_text("def target_fn():\n    return 1\n", encoding="utf-8")
    store.write_note(
        store.paths.decisions_dir / "0001-x.md",
        Frontmatter(type="decision"), "Never inline target_fn", "Call `target_fn`.",
    )
    graph_ops.map_repo(store, TorsorConfig())

    result = CliRunner().invoke(app, ["impact", "target_fn", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "Never inline target_fn" in result.stdout


def test_mcp_recall_accepts_a_symbol_filter(tmp_path):
    import anyio

    from torsor_helper.server import build_server

    _store(tmp_path)
    tools = {t.name: t for t in anyio.run(build_server(tmp_path).list_tools)}
    assert "symbol" in tools["recall"].inputSchema["properties"]


def test_an_index_built_before_mentions_gets_backfilled(tmp_path):
    """Without this, the feature returns nothing on every existing project and
    there is no way to tell that from "nothing was recorded about this symbol"."""
    from torsor_helper.embeddings import HashingEmbedder
    from torsor_helper.indexer import reindex

    store = _store(tmp_path)
    note = store.paths.decisions_dir / "0001-x.md"
    store.write_note(note, Frontmatter(type="decision"), "X", "We call `target_fn`.")
    conn = _indexed(store)
    try:
        # An index from before the table existed: rows gone, stamp gone.
        conn.execute("DELETE FROM note_symbols")
        conn.execute("DELETE FROM meta WHERE key='mentions_format'")
        conn.commit()

        stats = reindex(store, conn, HashingEmbedder(384))
        assert stats["indexed"] == 0, "backfilling must not re-embed the corpus"
        assert note.as_posix() in db.notes_mentioning(conn, "target_fn")
    finally:
        conn.close()


def test_backfill_runs_once(tmp_path):
    from torsor_helper.embeddings import HashingEmbedder
    from torsor_helper.indexer import reindex

    store = _store(tmp_path)
    store.write_note(store.paths.decisions_dir / "0001-x.md",
                     Frontmatter(type="decision"), "X", "We call `target_fn`.")
    conn = _indexed(store)
    try:
        conn.execute("DELETE FROM note_symbols")
        conn.commit()
        reindex(store, conn, HashingEmbedder(384))
        assert db.notes_mentioning(conn, "target_fn") == []
    finally:
        conn.close()
