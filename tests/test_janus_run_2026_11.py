"""Findings from running the trimmed build against janus (a 5 000-file monorepo)
on 2026-11-10 — see tests/test_config_upgrade.py and test_coach_staleness.py for
the two bigger ones. These are the small ones the self-hosted repo cannot show."""
import io
import warnings

from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def _store(tmp_path):
    paths = TorsorPaths(tmp_path)
    store = Store(paths)
    store.scaffold()
    return store


# --- update_active: one section at a time ------------------------------------
# Over MCP the tool demanded focus, progress AND open_questions on every call, so
# an agent that only finished a task had to re-state the other two or wipe them.

def test_update_active_with_only_progress_keeps_the_other_sections(tmp_path):
    store = _store(tmp_path)
    ops.update_active(store, focus="ship hooks", progress="step 1", open_questions="CI?")
    ops.update_active(store, progress="steps 1-2 done")
    active = store.read_note(store.paths.active_context).body
    assert "ship hooks" in active and "CI?" in active
    assert "steps 1-2 done" in store.read_note(store.paths.progress).body


def test_update_active_with_only_focus_keeps_progress(tmp_path):
    store = _store(tmp_path)
    ops.update_active(store, focus="a", progress="done so far", open_questions="q")
    ops.update_active(store, focus="b")
    assert "done so far" in store.read_note(store.paths.progress).body
    active = store.read_note(store.paths.active_context).body
    assert "## Current focus\nb" in active and "q" in active


def test_the_mcp_tool_accepts_a_single_section(tmp_path):
    import anyio

    from torsor_helper.server import build_server

    _store(tmp_path)
    res = anyio.run(lambda: build_server(tmp_path).call_tool("update_active", {"progress": "half way"}))
    assert not res.is_error, res.content[0].text


def test_the_cli_active_command_accepts_a_single_section(tmp_path):
    _store(tmp_path)
    res = runner.invoke(app, ["active", "--root", str(tmp_path), "--progress", "half way"])
    assert res.exit_code == 0, res.output


# --- impact: mention paths are project-relative --------------------------------
# On janus every "N note(s) mention X" line carried a 100-character absolute
# scratch path; the note is inside the project by construction.

def test_impact_mentions_are_project_relative(tmp_path):
    store = _store(tmp_path)
    (tmp_path / "pay.py").write_text("def charge_card():\n    return 1\n", encoding="utf-8")
    from torsor_helper.config import TorsorConfig

    config = TorsorConfig()
    ops.remember(store, "`charge_card` must stay idempotent")
    ops.map_repo(store, config, None, force=True)
    ops.recall(store, config, "charge_card")  # auto_index: the journal note is indexed, mentions recorded
    res = ops.impact(store, config, "charge_card")
    assert res["mentions"], res
    for m in res["mentions"]:
        assert not m["path"].startswith("/"), m["path"]
        assert m["path"].startswith(".torsor/")


# --- the CLI prints a warning as one line, not a traceback-shaped block --------
# Without the embeddings extra every command printed
#   .../cli.py:246: UserWarning: fastembed unavailable (...)
#     name = get_embedder(TorsorConfig()).name
# — the file, line and source line are torsor's, not the user's.

def test_cli_warnings_are_one_line():
    from torsor_helper.cli import _show_warning

    buf = io.StringIO()
    _show_warning(UserWarning("fastembed unavailable; falling back"), UserWarning, "x/cli.py", 246, file=buf)
    assert buf.getvalue() == "warning: fastembed unavailable; falling back\n"


def test_the_cli_installs_its_warning_format(tmp_path, monkeypatch):
    _store(tmp_path)
    from torsor_helper import cli

    monkeypatch.setattr(warnings, "showwarning", warnings.showwarning)  # restore after the test
    runner.invoke(app, ["stats", "--root", str(tmp_path)])
    assert warnings.showwarning is cli._show_warning
