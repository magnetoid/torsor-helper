"""The index is derived and disposable; nothing committed may be rebuilt from it.

`.torsor/.index/` is git-ignored, so it is absent on a fresh clone and removed
by `clean --deep`. `.torsor/map/` is committed. Any path that reads the index to
decide what a committed file should contain — or whether it should exist — will
eventually run with an empty index and quietly destroy the real thing.
"""
from __future__ import annotations

import shutil

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def _repo(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    for name in ("alpha", "beta", "gamma"):
        (tmp_path / f"{name}.py").write_text(f"def {name}_fn():\n    return 1\n")
    return store


def test_a_partial_map_with_no_index_does_not_shrink_the_overview(tmp_path):
    store = _repo(tmp_path)
    config = TorsorConfig()
    ops.map_repo(store, config)
    overview = store.paths.map_dir / "overview.md"
    assert all(n in overview.read_text(encoding="utf-8") for n in ("alpha", "beta", "gamma"))

    # What `clean --deep` does, and what a fresh clone looks like.
    shutil.rmtree(store.paths.index_dir)

    # What the post-commit hook does after a one-file commit.
    ops.map_repo(store, config, ["alpha.py"])

    text = overview.read_text(encoding="utf-8")
    for name in ("alpha", "beta", "gamma"):
        assert f"{name}.py" in text, f"{name} vanished from a committed file"


def test_a_partial_map_with_no_index_keeps_the_other_map_notes(tmp_path):
    store = _repo(tmp_path)
    config = TorsorConfig()
    ops.map_repo(store, config)
    before = {p.name for p in (store.paths.map_dir / "modules").glob("*.md")}

    shutil.rmtree(store.paths.index_dir)
    ops.map_repo(store, config, ["alpha.py"])

    after = {p.name for p in (store.paths.map_dir / "modules").glob("*.md")}
    assert before <= after


def test_clean_with_an_empty_index_does_not_delete_committed_map_notes(tmp_path):
    store = _repo(tmp_path)
    config = TorsorConfig()
    ops.map_repo(store, config)
    notes = {p.name for p in (store.paths.map_dir / "modules").glob("*.md")}
    assert len(notes) >= 3

    shutil.rmtree(store.paths.index_dir)
    ops.clean(store, config, apply=True)

    after = {p.name for p in (store.paths.map_dir / "modules").glob("*.md")}
    assert after == notes, "orphan detection treated an empty index as 'nothing is live'"


def test_clean_still_prunes_a_genuine_orphan(tmp_path):
    store = _repo(tmp_path)
    config = TorsorConfig()
    ops.map_repo(store, config)
    (tmp_path / "beta.py").unlink()
    ops.map_repo(store, config, force=True)

    ops.clean(store, config, apply=True)

    names = {p.name for p in (store.paths.map_dir / "modules").glob("*.md")}
    assert not any("beta" in n for n in names)
