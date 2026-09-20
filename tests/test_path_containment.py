"""Nothing outside the project root may be read or written through a torsor call.

`check_drift`, `verify` and `stale --mark` all take caller-supplied paths, and
the first two are MCP tools — an agent steered by a prompt injection can pass
whatever it likes. `pre_edit` already got this right; these pin the rest.
"""
from __future__ import annotations

from pathlib import Path

from torsor_helper import guard, operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths, contained
from torsor_helper.store import Store


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path / "project"))
    store.scaffold()
    return store


def _forbid_requests(store):
    ops.record_decision(
        store, title="No requests", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "*.py", "severity": "error"}],
    )


# --- the helper -------------------------------------------------------------

def test_contained_accepts_a_path_inside_the_root(tmp_path):
    assert contained(tmp_path, "a/b.py") == (tmp_path / "a" / "b.py").resolve()
    assert contained(tmp_path, tmp_path / "a.py") == (tmp_path / "a.py").resolve()


def test_contained_rejects_traversal_and_absolute_escapes(tmp_path):
    assert contained(tmp_path, "../outside.py") is None
    assert contained(tmp_path, "a/../../outside.py") is None
    assert contained(tmp_path, "/etc/passwd") is None


def test_contained_rejects_a_symlink_that_points_out(tmp_path):
    outside = tmp_path.parent / "secret.py"
    outside.write_text("import requests\n")
    link = tmp_path / "link.py"
    link.symlink_to(outside)
    assert contained(tmp_path, "link.py") is None


# --- guard.check_drift ------------------------------------------------------

def test_check_drift_ignores_a_file_outside_the_project(tmp_path):
    store = _store(tmp_path)
    _forbid_requests(store)
    outside = tmp_path / "outside.py"
    outside.write_text("import requests\n")

    assert guard.check_drift(store, [str(outside)]) == []
    assert guard.check_drift(store, ["../outside.py"]) == []


def test_check_drift_still_flags_a_file_inside_the_project(tmp_path):
    store = _store(tmp_path)
    _forbid_requests(store)
    (store.paths.root / "inside.py").write_text("import requests\n")

    assert [v.file for v in guard.check_drift(store, ["inside.py"])] == ["inside.py"]


def test_verify_does_not_reach_outside_the_project(tmp_path):
    store = _store(tmp_path)
    _forbid_requests(store)
    (tmp_path / "outside.py").write_text("import requests\n")

    verdict = ops.verify(store, TorsorConfig(), [str(tmp_path / "outside.py")])

    assert next(c for c in verdict["checks"] if c["name"] == "guard")["count"] == 0


# --- stale --mark writes ----------------------------------------------------

def test_stale_mark_never_writes_outside_the_project(tmp_path):
    store = _store(tmp_path)
    victim = tmp_path / "victim.md"
    victim.write_text("original\n", encoding="utf-8")

    changed = ops._set_note_status(store, ["../victim.md", "/etc/hosts"], "stale")

    assert changed == []
    assert victim.read_text(encoding="utf-8") == "original\n"


def test_stale_mark_still_marks_a_note_inside_the_project(tmp_path):
    store = _store(tmp_path)
    note = store.paths.memory_dir / "n.md"
    note.write_text("---\ntype: note\nstatus: active\n---\n\n# N\n\nbody\n", encoding="utf-8")
    rel = note.relative_to(store.paths.root).as_posix()

    assert ops._set_note_status(store, [rel], "stale") == [rel]
    assert "status: stale" in note.read_text(encoding="utf-8")


# --- the cartographer's explicit-paths mode --------------------------------

def test_map_repo_ignores_paths_outside_the_project(tmp_path):
    from torsor_helper import cartographer

    store = _store(tmp_path)
    (tmp_path / "outside.py").write_text("def leaked():\n    return 1\n")
    (store.paths.root / "inside.py").write_text("def kept():\n    return 1\n")

    syms = cartographer.scan_repo(store.paths.root, paths=["inside.py", str(tmp_path / "outside.py")])

    assert {s.name for s in syms} == {"kept"}


def test_map_repo_note_writes_stay_under_the_map_dir(tmp_path):
    store = _store(tmp_path)
    (store.paths.root / "a.py").write_text("def f():\n    return 1\n")
    ops.map_repo(store, TorsorConfig())
    written = list(store.paths.map_dir.rglob("*.md"))
    assert written
    for p in written:
        assert Path(p).resolve().is_relative_to(store.paths.map_dir.resolve())
