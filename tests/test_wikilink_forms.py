"""A wikilink's target is the part before the alias and the anchor.

`[[note|shown as this]]` and `[[note#a-heading]]` are ordinary Markdown-wiki
forms. Taking the raw inner text as the slug meant neither ever resolved to a
note — and worse, the staleness checker then reported both as dangling, which
is a false positive in the one detector built to have none (ADR 0010).
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


def test_alias_and_anchor_are_stripped_from_the_target():
    assert Store.extract_wikilinks("see [[charter]]") == ["charter"]
    assert Store.extract_wikilinks("see [[charter|the charter]]") == ["charter"]
    assert Store.extract_wikilinks("see [[charter#principles]]") == ["charter"]
    assert Store.extract_wikilinks("see [[charter#principles|the rules]]") == ["charter"]


def test_a_path_shaped_target_keeps_its_directory():
    # This one still means "the note at that path tail", not a basename.
    assert Store.extract_wikilinks("see [[architecture/decisions/0001-x]]") == \
        ["architecture/decisions/0001-x"]


def test_the_same_note_reached_two_ways_is_one_link():
    assert Store.extract_wikilinks("[[charter]] and [[charter#purpose]]") == ["charter"]


def test_an_empty_or_anchor_only_target_is_ignored():
    assert Store.extract_wikilinks("[[]] [[#section]] [[ | x ]]") == []


def test_an_aliased_link_to_a_real_note_resolves(tmp_path):
    store = _store(tmp_path)
    (store.paths.memory_dir / "target.md").write_text(
        "---\ntype: note\n---\n\n# Target\n\nbody\n", encoding="utf-8"
    )
    conn = db.connect(store.paths.index_db)
    try:
        db.upsert_note(conn, str(store.paths.memory_dir / "target.md"), "h", 4,
                       "note", None, "Target", "", "active")
        db.replace_edges(conn, "src.md", Store.extract_wikilinks("see [[target|the target]]"))
        assert db.neighbors(conn, "src.md") == [str(store.paths.memory_dir / "target.md")]
    finally:
        conn.close()


def test_staleness_does_not_call_an_aliased_link_dangling(tmp_path):
    store = _store(tmp_path)
    (store.paths.memory_dir / "target.md").write_text(
        "---\ntype: note\n---\n\n# Target\n\nbody\n", encoding="utf-8"
    )
    (store.paths.memory_dir / "src.md").write_text(
        "---\ntype: note\n---\n\n# Src\n\nSee [[target|the target]] and [[target#part]].\n",
        encoding="utf-8",
    )

    assert staleness.check_dangling_links(store) == []


def test_staleness_still_reports_a_genuinely_missing_target(tmp_path):
    store = _store(tmp_path)
    (store.paths.memory_dir / "src.md").write_text(
        "---\ntype: note\n---\n\n# Src\n\nSee [[gone|whatever]].\n", encoding="utf-8"
    )

    recs = staleness.check_dangling_links(store)
    assert len(recs) == 1
    assert "[[gone]]" in recs[0].message   # the target, not the alias
