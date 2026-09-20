"""Non-derivable state must not live in the directory whose whole point is that
it can be thrown away.

`coach_state.json` holds the user's dismissals and `capture_state.json` holds
the auto-handoff watermark. Neither rebuilds from Markdown, and both used to sit
in `.torsor/.index/`, which `clean --deep` removes wholesale — so a routine
cleanup silently un-dismissed every recommendation and made the next auto-handoff
replay the whole history.
"""
from __future__ import annotations

import json

from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.coach.state import CoachState
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    return store


def test_state_dir_is_beside_the_index_not_inside_it(tmp_path):
    paths = TorsorPaths(tmp_path)
    assert paths.state_dir == tmp_path / ".torsor" / "state"
    assert paths.index_dir not in paths.state_dir.parents


def test_dismissals_and_the_capture_watermark_land_in_state(tmp_path):
    store = _store(tmp_path)
    ops.dismiss_recommendation(store, "thin:charter.md")
    ops._save_capture_state(store, {"last_head": "abc"})

    assert (store.paths.state_dir / "coach_state.json").exists()
    assert (store.paths.state_dir / "capture_state.json").exists()


def test_a_deep_clean_keeps_them(tmp_path):
    store = _store(tmp_path)
    ops.dismiss_recommendation(store, "thin:charter.md")
    ops._save_capture_state(store, {"last_head": "abc"})

    result = runner.invoke(app, ["clean", "--root", str(tmp_path), "--apply", "--deep", "--yes"])

    assert result.exit_code == 0, result.output
    assert not store.paths.index_dir.exists()
    assert CoachState(store.paths.state_dir / "coach_state.json").is_dismissed("thin:charter.md")
    assert ops._load_capture_state(store)["last_head"] == "abc"


def test_state_written_by_an_older_version_is_migrated(tmp_path):
    store = _store(tmp_path)
    store.paths.index_dir.mkdir(parents=True, exist_ok=True)
    (store.paths.index_dir / "capture_state.json").write_text(
        json.dumps({"last_head": "old"}), encoding="utf-8"
    )
    (store.paths.index_dir / "coach_state.json").write_text(
        json.dumps({"thin:charter.md": {"dismissed": True}}), encoding="utf-8"
    )

    assert ops._load_capture_state(store)["last_head"] == "old"
    assert CoachState(ops._coach_state_path(store)).is_dismissed("thin:charter.md")


def test_init_git_ignores_the_state_dir(tmp_path):
    store = _store(tmp_path)
    ignored = (store.paths.base / ".gitignore").read_text(encoding="utf-8")
    assert ".index/" in ignored
    assert "state/" in ignored
