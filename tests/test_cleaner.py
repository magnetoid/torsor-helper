from datetime import datetime

from torsor_helper import cleaner, db
from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def _mapped(tmp_path, sources):
    """A project with `sources` written and fully mapped (map notes + index)."""
    store = _store(tmp_path)
    for name, body in sources.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    ops.map_repo(store, TorsorConfig())
    return store


def test_plan_flags_map_note_whose_source_file_is_gone(tmp_path):
    store = _mapped(tmp_path, {
        "keep.py": "def kept():\n    return 1\n",
        "gone.py": "def dropped():\n    return 2\n",
    })
    (tmp_path / "gone.py").unlink()

    plan = cleaner.plan(store, TorsorConfig())

    names = {p.name for p in plan.map_orphans}
    assert "gone.py.md" in names
    assert "keep.py.md" not in names


def test_plan_counts_index_rows_pointing_at_deleted_files(tmp_path):
    store = _mapped(tmp_path, {
        "keep.py": "def kept():\n    return 1\n",
        "gone.py": "def dropped():\n    return 2\n",
    })
    conn = db.connect(store.paths.index_db)
    db.save_complexity_snapshot(conn, {"keep.py": 3, "gone.py": 4})
    db.bump_path_access(conn, ["keep.py", "gone.py"])
    conn.close()
    (tmp_path / "gone.py").unlink()

    plan = cleaner.plan(store, TorsorConfig())

    assert plan.dead_rows["symbols"] == 1
    assert plan.dead_rows["complexity_snapshot"] == 1
    assert plan.dead_rows["path_access"] == 1


def _journal(store, date_str, body="## 09:00 · learning\n\nsomething\n"):
    path = store.paths.journal_file(date_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntype: journal\n---\n\n# Journal {date_str}\n\n{body}", encoding="utf-8")
    return path


def test_plan_expires_journals_older_than_the_retention_window(tmp_path):
    store = _store(tmp_path)
    old = _journal(store, "2026-01-01")   # 151 days before the fixed clock
    recent = _journal(store, "2026-05-20")  # 12 days before

    plan = cleaner.plan(store, TorsorConfig())

    assert old in plan.journal_expired
    assert recent not in plan.journal_expired


def test_retention_of_zero_days_disables_journal_expiry(tmp_path):
    store = _store(tmp_path)
    _journal(store, "2020-01-01")
    config = TorsorConfig()
    config.clean.journal_retention_days = 0

    assert cleaner.plan(store, config).journal_expired == []


def test_planning_alone_deletes_nothing(tmp_path):
    store = _mapped(tmp_path, {"gone.py": "def dropped():\n    return 2\n"})
    (tmp_path / "gone.py").unlink()
    orphan = store.paths.map_dir / "modules" / "gone.py.md"
    _journal(store, "2020-01-01")

    plan = cleaner.plan(store, TorsorConfig())

    assert plan.map_orphans and plan.journal_expired  # there was something to reclaim
    assert orphan.exists()
    assert store.paths.journal_file("2020-01-01").exists()


def test_apply_removes_orphaned_map_notes_and_expired_journals(tmp_path):
    store = _mapped(tmp_path, {
        "keep.py": "def kept():\n    return 1\n",
        "gone.py": "def dropped():\n    return 2\n",
    })
    (tmp_path / "gone.py").unlink()
    _journal(store, "2020-01-01")

    config = TorsorConfig()
    cleaner.apply(store, config, cleaner.plan(store, config))

    assert not (store.paths.map_dir / "modules" / "gone.py.md").exists()
    assert (store.paths.map_dir / "modules" / "keep.py.md").exists()
    assert not store.paths.journal_file("2020-01-01").exists()


def test_apply_mines_insights_before_discarding_a_journal(tmp_path):
    store = _store(tmp_path)
    _journal(store, "2020-01-01", "## 09:00 · learning\n\nprefer uv run\n")

    config = TorsorConfig()
    cleaner.apply(store, config, cleaner.plan(store, config))

    assert not store.paths.journal_file("2020-01-01").exists()
    assert "prefer uv run" in (store.paths.insights_dir / "learning.md").read_text()


def test_apply_never_touches_source_of_truth_or_code(tmp_path):
    store = _mapped(tmp_path, {"keep.py": "def kept():\n    return 1\n"})
    _journal(store, "2020-01-01")
    protected = [
        store.paths.charter, store.paths.config_file, store.paths.system_patterns,
        store.paths.tech_context, store.paths.active_context, store.paths.progress,
        tmp_path / "keep.py",
    ]
    before = {p: p.read_text() for p in protected if p.exists()}
    assert before  # the fixture really did create them

    config = TorsorConfig()
    cleaner.apply(store, config, cleaner.plan(store, config))

    assert {p: p.read_text() for p in before} == before


def test_deep_clean_drops_the_index_but_keeps_the_markdown(tmp_path):
    store = _mapped(tmp_path, {"keep.py": "def kept():\n    return 1\n"})

    config = TorsorConfig()
    cleaner.apply(store, config, cleaner.plan(store, config, deep=True))

    assert not store.paths.index_dir.exists()
    assert store.paths.charter.exists()
    assert (store.paths.map_dir / "modules" / "keep.py.md").exists()


def test_package_init_module_is_not_mistaken_for_an_orphan(tmp_path):
    """'pkg/__init__.py' mangles to 'pkg____init__.py.md' — a filename that
    reverse-parsing would misread. Detection must mangle forward, not back."""
    (tmp_path / "pkg").mkdir()
    store = _mapped(tmp_path, {"pkg/__init__.py": "def boot():\n    return 1\n"})

    assert cleaner.plan(store, TorsorConfig()).map_orphans == []
