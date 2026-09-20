"""Options that silently did something other than what they said.

Each of these fails the same way: no error, no warning, just different
behaviour from the one the user asked for.
"""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.config import TorsorConfig, load_config
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    return store


def test_auto_index_false_stops_reindexing_an_existing_index(tmp_path):
    """It only ever worked on a virgin project: once the DB existed, recall
    reindexed on every call regardless of the setting."""
    store = _store(tmp_path)
    config = TorsorConfig()
    (store.paths.memory_dir / "one.md").write_text(
        "---\ntype: note\n---\n\n# One\n\nwidget alpha\n", encoding="utf-8"
    )
    ops.recall(store, config, "widget")          # builds the index
    config.index.auto_index = False
    (store.paths.memory_dir / "two.md").write_text(
        "---\ntype: note\n---\n\n# Two\n\nwidget beta\n", encoding="utf-8"
    )

    hits = ops.recall(store, config, "widget").hits

    assert not any("Two" in h.title for h in hits), "reindexed despite auto_index = false"


def test_verify_reports_staleness_project_wide_on_purpose(tmp_path):
    """Not a gap. A staleness finding's source is a NOTE path, while `files`
    holds SOURCE files — git-changed discovery filters to source extensions, so
    a .md never appears in it. Filtering one namespace by the other would
    always yield nothing, which would read as "no staleness" rather than
    "not checked"."""
    store = _store(tmp_path)
    (store.paths.memory_dir / "rotten.md").write_text(
        "---\ntype: note\n---\n\n# Rotten\n\nSee [[gone-forever]].\n", encoding="utf-8"
    )
    (tmp_path / "clean.py").write_text("import os\n\ndef f():\n    return os.getcwd()\n")

    verdict = ops.verify(store, TorsorConfig(), ["clean.py"])

    assert next(c for c in verdict["checks"] if c["name"] == "staleness")["count"] >= 1


def test_a_typo_in_severity_is_rejected_not_silently_widened(tmp_path):
    """An unknown threshold mapped to cutoff 0, i.e. "fail on anything" — the
    opposite of a conservative default, and invisible in CI."""
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["guard", "--root", str(tmp_path), "--severity", "warnign"])
    assert result.exit_code == 2
    assert "warnign" in result.output or "severity" in result.output.lower()


def test_a_valid_severity_is_still_accepted(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["guard", "--root", str(tmp_path), "--severity", "error"])
    assert result.exit_code == 0, result.output


def test_mark_and_unmark_together_is_an_error(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    result = runner.invoke(app, ["stale", "--root", str(tmp_path), "--mark", "--unmark"])
    assert result.exit_code == 2


def test_importance_floors_accept_the_case_a_user_would_write(tmp_path):
    """Keyed by Tier.name, so a lowercase key in torsor.toml was ignored and
    decay silently stayed off."""
    paths = TorsorPaths(tmp_path)
    Store(paths).scaffold()
    paths.config_file.write_text(
        "version = 1\n\n[index.importance_floors]\nactive = 0.5\n", encoding="utf-8"
    )

    floors = load_config(paths).index.importance_floors

    assert floors["ACTIVE"] == pytest.approx(0.5)
