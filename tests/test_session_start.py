import json
from datetime import datetime

from typer.testing import CliRunner

from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 0, 0)
runner = CliRunner()


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    store.paths.charter.write_text(
        "---\ntype: charter\n---\n\n# Charter\n\n## Purpose\n\nShip the widget service.\n", encoding="utf-8"
    )
    return store


def test_session_start_context_is_a_budgeted_digest_with_a_no_recall_header(tmp_path):
    store = _store(tmp_path)
    config = TorsorConfig()

    text = ops.session_start_context(store, config, how="startup")

    assert text is not None
    assert "Ship the widget service" in text
    assert "bootstrap_session" in text  # tells the agent not to spend a call re-fetching this
    assert len(text) <= config.budgets.session_start_tokens * config.budgets.chars_per_token + 400


def test_session_start_context_is_disabled_by_config(tmp_path):
    store = _store(tmp_path)
    config = TorsorConfig()
    config.automation.auto_bootstrap = False

    assert ops.session_start_context(store, config, how="startup") is None


def test_session_start_context_reinjects_after_compaction(tmp_path):
    store = _store(tmp_path)

    text = ops.session_start_context(store, TorsorConfig(), how="compact")

    assert text is not None
    assert "Ship the widget service" in text


def test_hooks_run_session_start_emits_claude_code_hook_json(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    payload = json.dumps({"session_id": "s1", "how_session_started": "startup"})

    r = runner.invoke(app, ["hooks", "run", "session-start", "--root", str(tmp_path)], input=payload)

    assert r.exit_code == 0, r.output
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "torsor" in out["hookSpecificOutput"]["additionalContext"]
