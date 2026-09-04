"""A1: the PreToolUse edit gate. The guard runs against the *proposed* file
content before Claude Code applies an Edit/Write, ratcheted against the
baseline so only new drift surfaces. Advisory by default; blocking is opt-in."""
import json

from typer.testing import CliRunner

from torsor_helper import baseline, operations as ops
from torsor_helper.cli import app
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()

_ADR = """---
type: decision
status: accepted
rules:
- kind: forbid_import
  target: os
  scope: "*.py"
  severity: error
  message: no direct os access
---

# ADR 0001: No os

## Decision
Never import os.
"""


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (store.paths.decisions_dir / "0001-no-os.md").write_text(_ADR, encoding="utf-8")
    return store


def test_write_with_a_new_violation_is_advised(tmp_path):
    store = _store(tmp_path)

    verdict = ops.pre_edit(store, TorsorConfig(), "Write", {"file_path": str(tmp_path / "a.py"), "content": "import os\n"})

    assert verdict is not None
    assert verdict["decision"] == "advise"
    assert any(v.rule_kind == "forbid_import" for v in verdict["new"])
    assert "no direct os access" in verdict["context"]
    assert "ADR 0001" in verdict["context"]


def test_edit_is_checked_against_the_proposed_text_not_the_file_on_disk(tmp_path):
    store = _store(tmp_path)
    target = tmp_path / "a.py"
    target.write_text("import sys\n", encoding="utf-8")

    verdict = ops.pre_edit(store, TorsorConfig(), "Edit", {
        "file_path": str(target), "old_string": "import sys", "new_string": "import os",
    })

    assert verdict is not None and verdict["new"]
    assert target.read_text(encoding="utf-8") == "import sys\n"  # the gate never writes


def test_clean_edit_yields_no_verdict(tmp_path):
    store = _store(tmp_path)

    assert ops.pre_edit(store, TorsorConfig(), "Write", {"file_path": str(tmp_path / "a.py"), "content": "x = 1\n"}) is None


def test_baselined_violation_is_not_re_reported(tmp_path):
    store = _store(tmp_path)
    target = tmp_path / "a.py"
    target.write_text("import os\n", encoding="utf-8")
    baseline.save(store.paths.baseline_file, ops.check_drift(store, TorsorConfig(), ["a.py"]))

    verdict = ops.pre_edit(store, TorsorConfig(), "Edit", {
        "file_path": str(target), "old_string": "import os\n", "new_string": "import os\nx = 1\n",
    })

    assert verdict is None


def test_block_mode_denies_only_error_severity(tmp_path):
    store = _store(tmp_path)
    config = TorsorConfig()
    config.automation.guard_on_edit = "block"

    verdict = ops.pre_edit(store, config, "Write", {"file_path": str(tmp_path / "a.py"), "content": "import os\n"})

    assert verdict["decision"] == "deny"


def test_off_mode_is_silent(tmp_path):
    store = _store(tmp_path)
    config = TorsorConfig()
    config.automation.guard_on_edit = "off"

    assert ops.pre_edit(store, config, "Write", {"file_path": str(tmp_path / "a.py"), "content": "import os\n"}) is None


def test_non_python_and_unknown_tools_are_ignored(tmp_path):
    store = _store(tmp_path)
    assert ops.pre_edit(store, TorsorConfig(), "Write", {"file_path": str(tmp_path / "a.md"), "content": "import os"}) is None
    assert ops.pre_edit(store, TorsorConfig(), "Bash", {"command": "import os"}) is None


def test_hooks_run_pre_edit_emits_pre_tool_use_json(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / ".torsor" / "architecture" / "decisions" / "0001-no-os.md").write_text(_ADR, encoding="utf-8")
    payload = json.dumps({
        "hook_event_name": "PreToolUse", "tool_name": "Write",
        "tool_input": {"file_path": str(tmp_path / "a.py"), "content": "import os\n"},
    })

    r = runner.invoke(app, ["hooks", "run", "pre-edit", "--root", str(tmp_path)], input=payload)

    assert r.exit_code == 0, r.output
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert "no direct os access" in out["additionalContext"]
    assert "permissionDecision" not in out  # advisory by default


def test_hooks_run_pre_edit_block_mode_sets_deny(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / ".torsor" / "architecture" / "decisions" / "0001-no-os.md").write_text(_ADR, encoding="utf-8")
    from torsor_helper.config import load_config, save_config

    paths = TorsorPaths(tmp_path)
    config = load_config(paths)
    config.automation.guard_on_edit = "block"
    save_config(paths, config)
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "a.py"), "content": "import os\n"}})

    r = runner.invoke(app, ["hooks", "run", "pre-edit", "--root", str(tmp_path)], input=payload)

    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "ADR 0001" in out["permissionDecisionReason"]
