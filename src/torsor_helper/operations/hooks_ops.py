"""Installing, removing and reporting the auto-capture hooks.

CLI-only by design (ADR 0009): an agent should not rewrite the hooks that
govern it. Only the read-only status is exposed over MCP. Everything here
writes into files the user owns — .git/hooks and .claude/settings.json — so it
refuses rather than guesses when it cannot parse what is already there."""
from __future__ import annotations

import json

from torsor_helper import gitinfo
from torsor_helper import hooks as _hooks
from torsor_helper.operations.capture import _capture_state_path, _op_totals, _save_capture_state
from torsor_helper.operations.decisions import _next_adr_number


def install_hooks(store, config, *, git=True, claude=True, local=False, on_stop=False) -> dict:
    """Wire git hooks + Claude Code hook entries so capture fires on the lifecycle.
    Idempotent, foreign-content-preserving, and CLI-only (footgun parity with the
    self-updater — an agent should not rewrite its own hooks; ADR 0009)."""
    root = str(store.paths.root)
    result = {"git_hooks": [], "claude_settings": None, "warnings": [], "skipped": []}

    if git:
        hooks_dir = _hooks.resolve_hooks_dir(root)
        if hooks_dir is None:
            result["warnings"].append("not a git repo — git hooks skipped")
            result["skipped"].append("git")
        else:
            foreign = _hooks.foreign_hook_manager(root)
            if foreign:
                result["warnings"].append(
                    f"{foreign} manages git hooks here — add "
                    f'`torsor hooks run post-commit --root \"{root}\"` to your {foreign} '
                    "config instead of relying on .git/hooks"
                )
            pc = _hooks.write_git_hook(hooks_dir, "post-commit", _hooks.post_commit_script(root))
            result["git_hooks"].append(str(pc))
            if config.automation.guard_on_push:
                pp = _hooks.write_git_hook(hooks_dir, "pre-push", _hooks.pre_push_script(root))
                result["git_hooks"].append(str(pp))

    if claude:
        target = store.paths.claude_settings_local if local else store.paths.claude_settings
        sibling = store.paths.claude_settings if local else store.paths.claude_settings_local
        data, ok = _hooks.read_settings(target)
        if not ok:
            # The file holds the user's permissions, env and model. Merging into
            # {} would replace all of it with torsor's hooks, so refuse instead.
            result["warnings"].append(
                f"{target} exists but could not be parsed as JSON — left untouched. "
                "Claude Code tolerates comments and trailing commas; this parser does not. "
                "Fix or move it, then re-run `torsor hooks install`."
            )
            result["skipped"].append("claude")
        else:
            _hooks.write_settings(target, _hooks.merge_settings_hooks(data, root=".", on_stop=on_stop))
            result["claude_settings"] = str(target)
            # Exactly one install site: entries left behind in the sibling file
            # would fire every hook a second time (double digest, double handoff).
            if sibling.exists():
                other, other_ok = _hooks.read_settings(sibling)
                if other_ok:
                    cleaned = _hooks.merge_settings_hooks(other, remove=True)
                    if cleaned != other:
                        _hooks.write_settings(sibling, cleaned)
                        result["warnings"].append(f"removed a previous torsor install from {sibling}")

    # Baseline the capture marker at install time so the first auto-handoff is
    # scoped to post-install activity (not a dump of all prior commits/ADRs).
    if not _capture_state_path(store).exists():
        _save_capture_state(store, {
            "last_head": gitinfo.head(root),
            "op_snapshot": _op_totals(store),
            "adr_max": _next_adr_number(store) - 1,
        })
    return result

def uninstall_hooks(store, config, *, local=False) -> dict:
    """Remove only torsor-owned git hooks + Claude Code hook entries."""
    result = {"removed": [], "claude_settings": None, "cleaned": [], "warnings": []}
    hooks_dir = _hooks.resolve_hooks_dir(str(store.paths.root))
    if hooks_dir is not None:
        for name in ("post-commit", "pre-push"):
            removed = _hooks.write_git_hook(hooks_dir, name, "", remove=True)
            if removed is not None:
                result["removed"].append(str(removed))

    # Both files, always. `local` used to select one, which left the other one
    # firing while the user believed the hooks were gone. Uninstall means gone.
    for target in (store.paths.claude_settings, store.paths.claude_settings_local):
        if not target.exists():
            continue
        data, ok = _hooks.read_settings(target)
        if not ok:
            result["warnings"].append(
                f"{target} exists but could not be parsed as JSON — left untouched; "
                "remove torsor's hook entries by hand."
            )
            continue
        merged = _hooks.merge_settings_hooks(data, remove=True)
        if merged != data:
            _hooks.write_settings(target, merged)
            result["cleaned"].append(str(target))
    result["claude_settings"] = result["cleaned"][0] if result["cleaned"] else None
    return result

def hooks_status(store, config) -> dict:
    """Read-only report of which git hooks + Claude Code events carry a torsor
    entry. The only auto-capture surface exposed as an MCP tool (writes are CLI-only)."""
    status = {"git_repo": False, "git_hooks": {}, "claude_events": []}
    hooks_dir = _hooks.resolve_hooks_dir(str(store.paths.root))
    if hooks_dir is not None:
        status["git_repo"] = True
        for name in ("post-commit", "pre-push"):
            f = hooks_dir / name
            status["git_hooks"][name] = f.exists() and _hooks.is_managed_git_hook(f.read_text(encoding="utf-8"))

    events: list[str] = []
    for target in (store.paths.claude_settings, store.paths.claude_settings_local):
        if not target.exists():
            continue
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        events.extend(_hooks.settings_events_with_torsor(data))
    status["claude_events"] = sorted(set(events))
    return status
