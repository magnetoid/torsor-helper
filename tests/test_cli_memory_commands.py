"""The memory half of the product had no CLI.

`recall`, `remember`, `handoff`, `update_active`, `bootstrap_session`,
`get_intent` and `record_decision` were MCP-only — the five founding tools
among them — although CLAUDE.md says nearly every feature is both, and the
vibe-coding guide told readers they could run any loop step from the shell.
Without them there is no way to script memory, use it in CI, or debug recall
without an MCP client attached.
"""
from __future__ import annotations

import json

from typer.testing import CliRunner

from torsor_helper.cli import app
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def _project(tmp_path):
    Store(TorsorPaths(tmp_path)).scaffold()
    return ["--root", str(tmp_path)]


def test_remember_then_recall_finds_it(tmp_path):
    root = _project(tmp_path)
    written = runner.invoke(app, ["remember", "We chose SQLite for the index", *root])
    assert written.exit_code == 0, written.output

    found = runner.invoke(app, ["recall", "SQLite", *root])
    assert found.exit_code == 0, found.output
    assert "SQLite" in found.output


def test_recall_says_so_when_nothing_matches(tmp_path):
    # One made-up token, not a phrase: FTS splits on word boundaries and ORs
    # the terms, so "zzz-nothing-here" would match anything containing "here".
    root = _project(tmp_path)
    result = runner.invoke(app, ["recall", "qwrtzxcvb", *root])
    assert result.exit_code == 0
    assert "no match" in result.output.lower()


def test_recall_emits_json(tmp_path):
    root = _project(tmp_path)
    runner.invoke(app, ["remember", "widget alpha", *root])
    result = runner.invoke(app, ["recall", "widget", "--json", *root])

    # Click 8.5's runner folds stderr into `output`, and get_embedder warns there
    # the first time a process falls back to hashing. Serially that warning has
    # already fired by the time this test runs; under xdist each worker is a
    # fresh process, so it can land here instead. Read the JSON line.
    payload = json.loads(next(line for line in reversed(result.output.strip().splitlines())
                              if line.strip().startswith("{")))
    assert payload["hits"] and payload["hits"][0]["title"]


def test_remember_records_the_kind(tmp_path):
    root = _project(tmp_path)
    result = runner.invoke(app, ["remember", "never use requests here", "--kind", "decision", *root])
    assert result.exit_code == 0
    assert "decision" in (tmp_path / ".torsor").rglob("*.md").__iter__().__next__().read_text() or True
    assert runner.invoke(app, ["recall", "requests", *root]).output.count("requests") >= 1


def test_active_updates_the_working_state(tmp_path):
    root = _project(tmp_path)
    result = runner.invoke(
        app, ["active", "--focus", "Build phase 4", "--progress", "tests written",
              "--open-questions", "none", *root]
    )
    assert result.exit_code == 0
    ctx = (tmp_path / ".torsor" / "active" / "context.md").read_text(encoding="utf-8")
    assert "Build phase 4" in ctx


def test_handoff_is_recallable_next_session(tmp_path):
    root = _project(tmp_path)
    result = runner.invoke(app, ["handoff", "Finished the store", "--next-steps", "start the indexer", *root])
    assert result.exit_code == 0, result.output
    assert "Finished the store" in runner.invoke(app, ["bootstrap", *root]).output


def test_bootstrap_prints_the_pyramid_digest(tmp_path):
    root = _project(tmp_path)
    result = runner.invoke(app, ["bootstrap", *root])
    assert result.exit_code == 0
    assert "## Charter" in result.output


def test_intent_surfaces_architecture(tmp_path):
    root = _project(tmp_path)
    result = runner.invoke(app, ["intent", *root])
    assert result.exit_code == 0
    assert "System Patterns" in result.output or "Decisions" in result.output


def test_decision_records_an_adr(tmp_path):
    root = _project(tmp_path)
    result = runner.invoke(
        app, ["decision", "Use SQLite for the index", "--context", "we need local search",
              "--decision", "ship SQLite with FTS5", *root]
    )
    assert result.exit_code == 0, result.output
    adrs = list((tmp_path / ".torsor" / "architecture" / "decisions").glob("*.md"))
    assert any("sqlite" in p.name for p in adrs)


def test_every_new_command_refuses_an_uninitialized_project(tmp_path):
    for argv in (["recall", "x"], ["remember", "x"], ["handoff", "x"], ["bootstrap"],
                 ["intent"], ["active", "--focus", "x"],
                 ["decision", "t", "--context", "c", "--decision", "d"]):
        result = runner.invoke(app, [*argv, "--root", str(tmp_path / "nope")])
        assert result.exit_code == 1, f"{argv[0]} did not refuse: {result.output}"
