from datetime import datetime

from torsor_helper.models import Frontmatter, Tier
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def test_scaffold_creates_pyramid_and_gitignore(tmp_path):
    paths = TorsorPaths(tmp_path)
    Store(paths, clock=CLOCK).scaffold()
    assert paths.charter.exists()
    assert paths.system_patterns.exists()
    assert (paths.decisions_dir / "0001-adopt-torsor-helper.md").exists()
    assert paths.active_context.exists()
    assert paths.journal_dir.is_dir()
    assert (paths.base / ".gitignore").read_text().strip() == ".index/"


def test_scaffold_is_idempotent_without_force(tmp_path):
    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=CLOCK)
    store.scaffold()
    paths.charter.write_text("EDITED")
    store.scaffold()  # must not overwrite existing files
    assert paths.charter.read_text() == "EDITED"


def test_write_then_read_note(tmp_path):
    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=CLOCK)
    target = paths.memory_dir / "note.md"
    note = store.write_note(target, Frontmatter(type="observation"), "Hi", "Body here")
    assert target.exists()
    read = store.read_note(target)
    assert read.title == "Hi"
    assert "Body here" in read.body
    assert read.tier is Tier.EPISODIC
    assert read.content_hash == note.content_hash


def test_append_journal_uses_clock_date_and_kind(tmp_path):
    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=CLOCK)
    store.scaffold()
    path = store.append_journal("Learned X", kind="learning", links=["charter"])
    assert path == paths.journal_file("2026-06-01")
    text = path.read_text()
    assert "Learned X" in text
    assert "learning" in text
    assert "[[charter]]" in text
    store.append_journal("Learned Y", kind="observation", links=[])
    assert "Learned X" in path.read_text() and "Learned Y" in path.read_text()


def test_iter_notes_skips_index_dir(tmp_path):
    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=CLOCK)
    store.scaffold()
    paths.index_dir.mkdir(parents=True, exist_ok=True)
    (paths.index_dir / "junk.md").write_text("---\ntype: x\n---\n# Junk\n")
    titles = {n.title for n in store.iter_notes()}
    assert "Project Charter" in titles
    assert "Junk" not in titles


def test_write_note_does_not_mutate_caller_frontmatter(tmp_path):
    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=CLOCK)
    fm = Frontmatter(type="observation")
    store.write_note(paths.memory_dir / "a.md", fm, "A", "body")
    # the caller's object must remain un-stamped
    assert fm.created is None
    assert fm.updated is None


def test_iter_notes_skips_unreadable_files(tmp_path):
    import pytest

    paths = TorsorPaths(tmp_path)
    store = Store(paths, clock=CLOCK)
    store.scaffold()
    bad = paths.journal_dir / "bad.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"\xff\xfe not utf-8 \xff")
    with pytest.warns(UserWarning, match="bad.md"):
        notes = list(store.iter_notes())
    assert notes  # the seeded notes still come through
    assert all(n.path != bad for n in notes)
