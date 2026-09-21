"""Team memory: what happens when two branches write .torsor/ at the same time.

The integration tests here drive a real git merge rather than asserting on our
own strings, because the thing being tested *is* git's behaviour — and the one
failure mode that matters (an attributes file naming a driver the clone has not
registered) is silent: git prints no warning and falls back to the normal text
merge, which looks exactly like not having configured anything at all.
"""
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from torsor_helper import merge
from torsor_helper.config import TorsorConfig, load_config, save_config
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

FIXED_CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _git(root, *args, check=True):
    # -c core.editor=true: `git merge` opens an editor for the merge message by
    # default, and with no TTY that hangs the suite rather than failing it.
    return subprocess.run(
        ["git", "-C", str(root), "-c", "core.editor=true", *args],
        check=check, capture_output=True, text=True,
    )


@pytest.fixture
def two_branches(tmp_path):
    """A repo with a scaffolded .torsor/ committed on `main`, ready to fork."""
    store = Store(TorsorPaths(tmp_path), clock=FIXED_CLOCK)
    store.scaffold()
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "scaffold")
    return tmp_path


# ---- the committed half: .gitattributes ----

def test_scaffold_writes_gitattributes(tmp_project):
    text = (Path(tmp_project) / ".torsor" / ".gitattributes").read_text(encoding="utf-8")
    assert "memory/journal/*.md merge=union" in text
    assert f"map/** merge={merge.DRIVER_NAME}" in text


def test_gitattributes_is_not_git_ignored(tmp_project):
    """It has to travel with the repo — a git-ignored one helps nobody else."""
    ignored = (Path(tmp_project) / ".torsor" / ".gitignore").read_text(encoding="utf-8")
    assert ".gitattributes" not in ignored


def test_write_attributes_preserves_foreign_lines(tmp_project):
    paths = TorsorPaths(tmp_project)
    target = paths.gitattributes
    target.write_text("*.bin binary\n", encoding="utf-8")
    merge.write_attributes(paths)
    text = target.read_text(encoding="utf-8")
    assert "*.bin binary" in text
    assert "memory/journal/*.md merge=union" in text


def test_write_attributes_is_idempotent(tmp_project):
    paths = TorsorPaths(tmp_project)
    merge.write_attributes(paths)
    once = paths.gitattributes.read_text(encoding="utf-8")
    merge.write_attributes(paths)
    assert paths.gitattributes.read_text(encoding="utf-8") == once


# ---- the local half: the merge driver ----

def test_driver_is_not_registered_by_default(two_branches):
    assert merge.driver_registered(two_branches) is False


def test_register_driver_writes_local_git_config(two_branches):
    assert merge.register_driver(two_branches) is True
    assert merge.driver_registered(two_branches) is True
    value = _git(two_branches, "config", "--get", merge.DRIVER_KEY).stdout.strip()
    assert "torsor" in value and "%A" in value


def test_status_reports_the_silent_gap(two_branches):
    """Attributes committed, driver unregistered: the case git says nothing about."""
    status = merge.status(two_branches, TorsorPaths(two_branches))
    assert status["attributes"] is True
    assert status["driver_registered"] is False
    merge.register_driver(two_branches)
    assert merge.status(two_branches, TorsorPaths(two_branches))["driver_registered"] is True


def test_status_outside_a_git_repo_does_not_raise(tmp_project):
    status = merge.status(tmp_project, TorsorPaths(tmp_project))
    assert status["git_repo"] is False
    assert status["driver_registered"] is False


def test_resolve_map_note_keeps_ours_and_records_it(tmp_project):
    paths = TorsorPaths(tmp_project)
    ours = paths.map_dir / "modules" / "a.py.md"
    ours.parent.mkdir(parents=True, exist_ok=True)
    ours.write_text("ours\n", encoding="utf-8")
    assert merge.resolve_map_note(paths, ours, "map/modules/a.py.md") == 0
    assert ours.read_text(encoding="utf-8") == "ours\n"
    assert merge.pending_regeneration(paths) == ["map/modules/a.py.md"]


def test_pending_regeneration_deduplicates(tmp_project):
    paths = TorsorPaths(tmp_project)
    note = paths.map_dir / "overview.md"
    note.write_text("x\n", encoding="utf-8")
    merge.resolve_map_note(paths, note, "map/overview.md")
    merge.resolve_map_note(paths, note, "map/overview.md")
    assert merge.pending_regeneration(paths) == ["map/overview.md"]


def test_clear_pending_regeneration(tmp_project):
    paths = TorsorPaths(tmp_project)
    note = paths.map_dir / "overview.md"
    note.write_text("x\n", encoding="utf-8")
    merge.resolve_map_note(paths, note, "map/overview.md")
    merge.clear_pending(paths)
    assert merge.pending_regeneration(paths) == []


# ---- journals: deterministic headers so union merge only unions entries ----

def test_journal_frontmatter_does_not_carry_the_wall_clock(tmp_project):
    """Two agents starting the same day's journal at different moments must
    write a byte-identical header, or union merge unions the frontmatter too."""
    early = Store(TorsorPaths(tmp_project), clock=lambda: datetime(2026, 6, 1, 9, 0, 0))
    late = Store(TorsorPaths(tmp_project), clock=lambda: datetime(2026, 6, 1, 17, 45, 0))

    path = early.append_journal("first", kind="learning", links=[])
    head_early = path.read_text(encoding="utf-8").split("\n---\n")[0]
    path.unlink()
    path = late.append_journal("second", kind="learning", links=[])
    head_late = path.read_text(encoding="utf-8").split("\n---\n")[0]

    assert head_early == head_late
    assert "09:00" not in head_early and "17:45" not in head_late


def test_journal_entries_still_carry_the_time(tmp_project):
    store = Store(TorsorPaths(tmp_project), clock=lambda: datetime(2026, 6, 1, 17, 45, 0))
    text = store.append_journal("second", kind="learning", links=[]).read_text(encoding="utf-8")
    assert "## 17:45 · learning" in text


def test_journal_updated_is_the_journal_date(tmp_project):
    store = Store(TorsorPaths(tmp_project), clock=FIXED_CLOCK)
    note = store.read_note(store.append_journal("x", kind="learning", links=[]))
    assert note.frontmatter.updated.startswith("2026-06-01")
    assert note.frontmatter.created == note.frontmatter.updated


# ---- journal partitioning ----

def test_partition_date_is_the_default(tmp_project):
    store = Store(TorsorPaths(tmp_project), clock=FIXED_CLOCK)
    assert store.append_journal("x", kind="learning", links=[]).name == "2026-06-01.md"


def test_partition_date_author_suffixes_the_file(two_branches):
    store = Store(TorsorPaths(two_branches), clock=FIXED_CLOCK, journal_partition="date-author")
    assert store.append_journal("x", kind="learning", links=[]).name == "2026-06-01.t.md"


def test_partition_falls_back_without_a_git_identity(tmp_project, monkeypatch):
    """No identity is not an error — it just means no partition to apply.

    Monkeypatched rather than run outside a repo, because `git config --get`
    walks up to the user's global config and finds an identity there even when
    the directory is not a repo at all."""
    from torsor_helper import gitinfo

    monkeypatch.setattr(gitinfo, "config_get", lambda root, key: "")
    store = Store(TorsorPaths(tmp_project), clock=FIXED_CLOCK, journal_partition="date-author")
    assert store.append_journal("x", kind="learning", links=[]).name == "2026-06-01.md"


@pytest.mark.parametrize(
    "identity,expected",
    [
        ("marko.tiosavljevic@gmail.com", "marko-tiosavljevic"),
        ("Ana Novi\u0107", "ana-novi"),
        ("a@b.c", "a"),
        ("...", ""),
    ],
)
def test_author_slug_is_filename_safe(monkeypatch, identity, expected):
    from torsor_helper import gitinfo

    monkeypatch.setattr(gitinfo, "config_get", lambda root, key: identity if key == "user.email" else "")
    assert gitinfo.author_slug(".") == expected


def test_partitioned_journals_still_expire(two_branches):
    """cleaner parses the date out of the filename; a suffix must not hide it."""
    from torsor_helper import cleaner

    store = Store(
        TorsorPaths(two_branches),
        clock=lambda: datetime(2020, 1, 1, 9, 0, 0),
        journal_partition="date-author",
    )
    old = store.append_journal("ancient", kind="learning", links=[])
    store.clock = FIXED_CLOCK
    plan = cleaner.plan(store, TorsorConfig())
    assert old in plan.journal_expired


def test_config_rejects_an_unknown_partition(tmp_project):
    from pydantic import ValidationError

    paths = TorsorPaths(tmp_project)
    paths.config_file.write_text(
        '[memory]\njournal_partition = "per-agent"\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        load_config(paths)


def test_config_round_trips_the_partition(tmp_project):
    paths = TorsorPaths(tmp_project)
    config = TorsorConfig()
    config.memory.journal_partition = "date-author"
    save_config(paths, config)
    assert load_config(paths).memory.journal_partition == "date-author"


# ---- integration: an actual concurrent merge ----

def _fork(root, branch, clock_hour, content):
    _git(root, "checkout", "-q", "-b", branch)
    store = Store(TorsorPaths(root), clock=lambda: datetime(2026, 6, 1, clock_hour, 0, 0))
    store.append_journal(content, kind="learning", links=[])
    _git(root, "add", "-A")
    _git(root, "commit", "-m", branch)
    _git(root, "checkout", "-q", "main")


def test_concurrent_journals_merge_without_conflict(two_branches):
    root = two_branches
    _fork(root, "feature", 10, "learned on the feature branch")
    store = Store(TorsorPaths(root), clock=lambda: datetime(2026, 6, 1, 9, 0, 0))
    store.append_journal("learned on main", kind="learning", links=[])
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "main work")

    result = _git(root, "merge", "feature", check=False)
    assert result.returncode == 0, result.stdout + result.stderr

    text = (root / ".torsor" / "memory" / "journal" / "2026-06-01.md").read_text(encoding="utf-8")
    assert "learned on main" in text
    assert "learned on the feature branch" in text
    assert "<<<<<<<" not in text
    # The header must not have been unioned along with the entries.
    assert text.count("type: journal") == 1
    assert text.count("created:") == 1


def test_merged_journal_still_parses_as_one_note(two_branches):
    root = two_branches
    _fork(root, "feature", 10, "feature insight")
    store = Store(TorsorPaths(root), clock=lambda: datetime(2026, 6, 1, 9, 0, 0))
    store.append_journal("main insight", kind="learning", links=[])
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "main work")
    _git(root, "merge", "feature")

    from torsor_helper.coach.mining import parse_journal_entries

    note = store.read_note(root / ".torsor" / "memory" / "journal" / "2026-06-01.md")
    assert note.frontmatter.type == "journal"
    kinds = [k for k, _ in parse_journal_entries(note.body)]
    assert kinds == ["learning", "learning"]


def test_map_conflict_is_resolved_by_the_driver(two_branches):
    root = two_branches
    merge.register_driver(root)
    note = root / ".torsor" / "map" / "overview.md"

    _git(root, "checkout", "-q", "-b", "feature")
    note.write_text("# Map\n\nfeature version\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "feature map")
    _git(root, "checkout", "-q", "main")
    note.write_text("# Map\n\nmain version\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "main map")

    result = _git(root, "merge", "feature", check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "<<<<<<<" not in note.read_text(encoding="utf-8")
    assert merge.pending_regeneration(TorsorPaths(root)) == ["map/overview.md"]


def test_without_the_driver_the_map_conflicts(two_branches):
    """The negative control. If this ever passes, the driver is not what is
    resolving the merge and the positive test above proves nothing."""
    root = two_branches
    note = root / ".torsor" / "map" / "overview.md"

    _git(root, "checkout", "-q", "-b", "feature")
    note.write_text("# Map\n\nfeature version\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "feature map")
    _git(root, "checkout", "-q", "main")
    note.write_text("# Map\n\nmain version\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "main map")

    assert _git(root, "merge", "feature", check=False).returncode != 0
