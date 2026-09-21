"""Functions that had no direct test, ranked by what happens when they break.

`pre_push` is the only hook that can block a push. `_transcript_digest` parses
a third-party JSONL file. `_scope_to_paths_glob` decides whether a rule loads
at all in Claude Code. `check_dependencies` is the orchestration both the deps
tool and the CLI go through. None of them had a test of its own.
"""
from __future__ import annotations

import json

from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.config import TorsorConfig
from torsor_helper.operations.capture import _transcript_digest
from torsor_helper.operations.prompt_blocks import _scope_to_paths_glob
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    return store


# --- pre_push: the one hook that can stop you shipping ----------------------

def _git_repo(tmp_path):
    """pre_push reads git-changed files, so it needs a real repo to have
    anything to look at."""
    import subprocess

    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    git("config", "commit.gpgsign", "false")
    (tmp_path / "seed.txt").write_text("x\n")
    git("add", "seed.txt")
    git("commit", "-m", "seed")


def _forbid_requests(store):
    ops.record_decision(
        store, title="No requests", context="c", decision="d",
        rules=[{"kind": "forbid_import", "target": "requests", "scope": "*.py", "severity": "error"}],
    )


def test_pre_push_is_a_no_op_when_the_gate_is_off(tmp_path):
    store = _store(tmp_path)
    _git_repo(tmp_path)
    _forbid_requests(store)
    (tmp_path / "bad.py").write_text("import requests\n")
    config = TorsorConfig()
    config.automation.guard_on_push = False

    verdict = ops.pre_push(store, config)

    assert verdict["skipped"] is True
    assert verdict["failed"] is False


def test_pre_push_fails_on_new_error_drift_when_enabled(tmp_path):
    store = _store(tmp_path)
    _git_repo(tmp_path)
    _forbid_requests(store)
    (tmp_path / "bad.py").write_text("import requests\n")
    config = TorsorConfig()
    config.automation.guard_on_push = True

    verdict = ops.pre_push(store, config)

    assert verdict["failed"] is True
    assert verdict["new"]


def test_pre_push_does_not_fail_on_baselined_drift(tmp_path):
    store = _store(tmp_path)
    _git_repo(tmp_path)
    _forbid_requests(store)
    (tmp_path / "bad.py").write_text("import requests\n")
    config = TorsorConfig()
    config.automation.guard_on_push = True
    ops.guard_run(store, config, update_baseline=True)

    assert ops.pre_push(store, config)["failed"] is False


# --- a transcript is a third party's file -----------------------------------

def test_a_missing_transcript_is_not_an_error(tmp_path):
    assert _transcript_digest(tmp_path / "nope.jsonl") == ""


def test_a_malformed_transcript_line_is_skipped(tmp_path):
    path = tmp_path / "t.jsonl"
    # It collects `file_path` values, wherever they are nested — deliberately
    # generic, so a Claude Code schema tweak cannot break it.
    path.write_text(
        "not json\n"
        + json.dumps({"type": "assistant",
                      "message": {"content": [{"input": {"file_path": "src/a.py"}}]}}) + "\n"
        + "{\n",
        encoding="utf-8",
    )

    assert "src/a.py" in _transcript_digest(path)


def test_an_empty_transcript_yields_nothing(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text("", encoding="utf-8")
    assert _transcript_digest(path) == ""


# --- the glob that decides whether a rule loads at all ----------------------

def test_a_bare_scope_becomes_a_recursive_glob():
    assert _scope_to_paths_glob("*.py") == "**/*.py"


def test_a_directory_scope_is_passed_through():
    assert _scope_to_paths_glob("src/torsor_helper/**/*.py") == "src/torsor_helper/**/*.py"


def test_an_empty_scope_falls_back_to_python():
    assert _scope_to_paths_glob("") == "**/*.py"


# --- check_dependencies, and the four commands with no adapter test --------

def test_check_dependencies_flags_a_phantom_import(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "x.py").write_text("import deffinitely_not_a_package\n")

    findings = ops.check_dependencies(store, TorsorConfig(), ["x.py"])

    assert any(f["name"] == "deffinitely_not_a_package" for f in findings)


def test_check_dependencies_is_quiet_about_the_standard_library(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "x.py").write_text("import os\nimport json\n")
    assert ops.check_dependencies(store, TorsorConfig(), ["x.py"]) == []


def test_deps_export_find_and_impact_have_a_working_cli(tmp_path):
    root = ["--root", str(tmp_path)]
    runner.invoke(app, ["init", *root])
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "core.py").write_text("def engine():\n    return 1\n")
    (tmp_path / "app.py").write_text("from pkg.core import engine\n\ndef run():\n    return engine()\n")
    runner.invoke(app, ["map", *root])

    for argv in (["deps", *root], ["export", *root], ["find", "engine", *root],
                 ["impact", "engine", *root]):
        result = runner.invoke(app, argv)
        assert result.exit_code == 0, f"torsor {argv[0]}: {result.output}"

    assert "app.py" in runner.invoke(app, ["impact", "engine", *root]).output
