"""Frontmatter is hand-edited, so one awkward note must not lose its metadata.

The parser is already best-effort in the sense that it never raises. What it
did instead was throw the whole block away on any single problem — so a note
with a scalar `tags:` lost its status, its rules and its type too.
"""
from __future__ import annotations

from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    return store


def test_a_byte_order_mark_does_not_hide_the_frontmatter(tmp_path):
    # Windows editors write one, and cartographer/guard/deps all read utf-8-sig
    # for exactly this reason. read_note did not, so a BOM'd note silently
    # became type="note" and lost its tier metadata.
    store = _store(tmp_path)
    path = store.paths.memory_dir / "bom.md"
    path.write_text("﻿---\ntype: decision\nstatus: superseded\n---\n\n# T\n\nbody\n",
                    encoding="utf-8")

    note = store.read_note(path)

    assert note.frontmatter.type == "decision"
    assert note.frontmatter.status == "superseded"


def test_a_scalar_tags_value_is_coerced_not_fatal(tmp_path):
    store = _store(tmp_path)
    path = store.paths.memory_dir / "scalar.md"
    path.write_text("---\ntype: decision\nstatus: superseded\ntags: architecture\n---\n\n# T\n\nb\n",
                    encoding="utf-8")

    fm = store.read_note(path).frontmatter

    assert fm.tags == ["architecture"]
    assert fm.type == "decision"        # the rest of the block survives
    assert fm.status == "superseded"


def test_a_scalar_links_value_is_coerced_too(tmp_path):
    store = _store(tmp_path)
    path = store.paths.memory_dir / "links.md"
    path.write_text("---\ntype: note\nlinks: charter\n---\n\n# T\n\nb\n", encoding="utf-8")

    assert store.read_note(path).frontmatter.links == ["charter"]


def test_kind_and_rules_are_declared_fields(tmp_path):
    # Both are schema-significant — `kind` is an indexed column and a search
    # filter, `rules` is what the guard enforces — and both survived only via
    # extra="allow", so a typo'd key was silently a no-op.
    store = _store(tmp_path)
    path = store.paths.memory_dir / "k.md"
    path.write_text(
        "---\ntype: decision\nkind: learning\nrules:\n  - kind: forbid_import\n"
        "    target: requests\n    scope: '*.py'\n---\n\n# T\n\nb\n",
        encoding="utf-8",
    )

    fm = store.read_note(path).frontmatter

    assert fm.kind == "learning"
    assert isinstance(fm.rules, list) and fm.rules[0]["target"] == "requests"


def test_a_genuinely_broken_block_still_degrades_quietly(tmp_path):
    store = _store(tmp_path)
    path = store.paths.memory_dir / "bad.md"
    path.write_text("---\n: : :\n  - [\n---\n\n# T\n\nbody\n", encoding="utf-8")

    note = store.read_note(path)

    assert note.frontmatter.type == "note"
    assert "body" in note.body
