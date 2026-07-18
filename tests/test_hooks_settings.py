"""Pure-module tests for merging torsor hook entries into .claude/settings.json.
Foreign hooks and other keys must survive; torsor entries must be idempotent
and surgically removable — mirrors the write_mcp_json merge guarantees."""
from torsor_helper import hooks


def _commands(data, event):
    out = []
    for group in data.get("hooks", {}).get(event, []):
        for h in group.get("hooks", []):
            out.append(h.get("command", ""))
    return out


def test_install_adds_session_end_entry():
    data = hooks.merge_settings_hooks({}, root=".")
    cmds = _commands(data, "SessionEnd")
    assert any("torsor hooks run session-end" in c for c in cmds)


def test_install_is_idempotent():
    data = hooks.merge_settings_hooks({}, root=".")
    twice = hooks.merge_settings_hooks(data, root=".")
    assert len(_commands(twice, "SessionEnd")) == 1


def test_preserves_foreign_hooks_and_keys():
    existing = {
        "model": "opus",
        "hooks": {
            "SessionEnd": [{"hooks": [{"type": "command", "command": "my-own-thing"}]}],
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "guard.sh"}]}],
        },
    }
    data = hooks.merge_settings_hooks(existing, root=".")
    assert data["model"] == "opus"  # foreign top-level key preserved
    assert "my-own-thing" in _commands(data, "SessionEnd")  # foreign SessionEnd group preserved
    assert "guard.sh" in _commands(data, "PreToolUse")  # foreign event preserved
    assert any("torsor hooks run session-end" in c for c in _commands(data, "SessionEnd"))


def test_uninstall_removes_only_torsor_entries():
    existing = {"hooks": {"SessionEnd": [{"hooks": [{"type": "command", "command": "my-own-thing"}]}]}}
    installed = hooks.merge_settings_hooks(existing, root=".")
    removed = hooks.merge_settings_hooks(installed, root=".", remove=True)
    cmds = _commands(removed, "SessionEnd")
    assert "my-own-thing" in cmds
    assert not any("torsor hooks run" in c for c in cmds)


def test_uninstall_drops_empty_event_key():
    installed = hooks.merge_settings_hooks({}, root=".")
    removed = hooks.merge_settings_hooks(installed, root=".", remove=True)
    assert "SessionEnd" not in removed.get("hooks", {})


def test_on_stop_uses_stop_event_and_switches_cleanly():
    session = hooks.merge_settings_hooks({}, root=".")
    stop = hooks.merge_settings_hooks(session, root=".", on_stop=True)
    # torsor entry moved to Stop; no stale torsor entry left under SessionEnd
    assert any("torsor hooks run session-end" in c for c in _commands(stop, "Stop"))
    assert not any("torsor hooks run" in c for c in _commands(stop, "SessionEnd"))


def test_non_dict_input_resets():
    data = hooks.merge_settings_hooks("garbage", root=".")
    assert any("torsor hooks run session-end" in c for c in _commands(data, "SessionEnd"))
