"""Safety contract for the auto-capture installer.

`torsor hooks install` writes into two files the user owns and did not create:
`.git/hooks/*` and `.claude/settings.json`. Anything it cannot parse it must
leave alone, and anything it did not write it must not remove. These are the
regressions that make that true.
"""
from __future__ import annotations

import json
import shlex

import pytest

from torsor_helper import hooks
from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    return store


def _commands(data, event):
    return [h.get("command", "")
            for group in data.get("hooks", {}).get(event, [])
            for h in group.get("hooks", [])]


# --- never destroy a settings file we cannot parse -------------------------

JSONC = """{
  // Claude Code accepts comments here; json.loads does not.
  "model": "opus",
  "permissions": {"allow": ["Bash(ls:*)"]}
}
"""


def test_install_refuses_to_overwrite_unparseable_settings(tmp_path):
    store = _store(tmp_path)
    target = store.paths.claude_settings
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(JSONC, encoding="utf-8")

    result = ops.install_hooks(store, TorsorConfig(), git=False)

    assert target.read_text(encoding="utf-8") == JSONC   # byte-identical
    assert result["claude_settings"] is None
    assert any("could not be parsed" in w for w in result["warnings"])
    assert "claude" in result["skipped"]


def test_uninstall_refuses_to_overwrite_unparseable_settings(tmp_path):
    store = _store(tmp_path)
    target = store.paths.claude_settings
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(JSONC, encoding="utf-8")

    result = ops.uninstall_hooks(store, TorsorConfig())

    assert target.read_text(encoding="utf-8") == JSONC
    assert any("could not be parsed" in w for w in result["warnings"])


def test_install_still_writes_when_settings_is_absent_or_valid(tmp_path):
    store = _store(tmp_path)

    result = ops.install_hooks(store, TorsorConfig(), git=False)

    data = json.loads(store.paths.claude_settings.read_text(encoding="utf-8"))
    assert result["claude_settings"] is not None
    assert any("session-start" in c for c in _commands(data, "SessionStart"))


# --- never remove a hook we did not write ----------------------------------

def test_a_group_holding_both_a_torsor_and_a_foreign_hook_keeps_the_foreign_one():
    existing = {"hooks": {"SessionEnd": [
        {"hooks": [
            {"type": "command", "command": "torsor hooks run session-end --root ."},
            {"type": "command", "command": "my-own-backup.sh"},
        ]},
    ]}}

    out = hooks.merge_settings_hooks(existing, root=".", remove=True)

    assert _commands(out, "SessionEnd") == ["my-own-backup.sh"]


def test_a_foreign_wrapper_that_merely_mentions_torsor_is_not_ours():
    existing = {"hooks": {"SessionEnd": [
        {"hooks": [{"type": "command", "command": "my-wrapper --then 'torsor hooks run session-end'"}]},
    ]}}

    out = hooks.merge_settings_hooks(existing, root=".", remove=True)

    assert _commands(out, "SessionEnd") == ["my-wrapper --then 'torsor hooks run session-end'"]


# --- exactly one install site ----------------------------------------------

def test_installing_locally_clears_a_previous_global_install(tmp_path):
    store = _store(tmp_path)
    ops.install_hooks(store, TorsorConfig(), git=False)               # global first

    ops.install_hooks(store, TorsorConfig(), git=False, local=True)   # then local

    glob = json.loads(store.paths.claude_settings.read_text(encoding="utf-8"))
    loc = json.loads(store.paths.claude_settings_local.read_text(encoding="utf-8"))
    assert _commands(glob, "SessionStart") == []   # would otherwise fire twice
    assert len(_commands(loc, "SessionStart")) == 1


def test_uninstall_clears_both_settings_files(tmp_path):
    store = _store(tmp_path)
    ops.install_hooks(store, TorsorConfig(), git=False)
    ops.install_hooks(store, TorsorConfig(), git=False, local=True)

    ops.uninstall_hooks(store, TorsorConfig())

    for path in (store.paths.claude_settings, store.paths.claude_settings_local):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert _commands(data, "SessionStart") == []
        assert _commands(data, "SessionEnd") == []


# --- the generated shell must survive an awkward project path --------------

@pytest.mark.parametrize("script", [hooks.post_commit_script, hooks.pre_push_script])
def test_git_hook_scripts_quote_the_project_root(script):
    evil = '/tmp/repo"; touch /tmp/pwned; #'

    body = script(evil)

    assert shlex.quote(evil) in body
    assert '"' + evil + '"' not in body
