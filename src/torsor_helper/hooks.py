from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

# Pure core for the auto-capture hook layer: script templates, the managed-block
# git-hook writer, the .claude/settings.json merge, and git-layout resolution.
# NO adapter imports (ADR 0002) and NO side effects beyond the explicit file
# writer — orchestration lives in operations.py. Everything here is deterministic.

_GIT_START = "# >>> torsor managed >>>"
_GIT_END = "# <<< torsor managed <<<"
_SHEBANG = "#!/bin/sh"

# A torsor-owned entry in .claude/settings.json is one whose command IS a
# torsor invocation, not merely one that mentions it. Matching the bare
# substring claimed ownership of any foreign wrapper that happened to call us
# (`my-wrapper --then 'torsor hooks run …'`) and removed it on uninstall.
_SENTINEL = "torsor hooks run"


def _is_torsor_command(command) -> bool:
    return str(command).strip().startswith(_SENTINEL + " ")


def _managed_block(inner: str) -> str:
    return f"{_GIT_START}\n{inner}\n{_GIT_END}"


def post_commit_script(root: str) -> str:
    """Advisory: refresh the map/snapshot for the just-committed files. A missing
    `torsor` binary must never break a commit, so guard on it and always exit 0."""
    inner = (
        "command -v torsor >/dev/null 2>&1 || exit 0\n"
        f"torsor hooks run post-commit --root {shlex.quote(str(root))} >/dev/null 2>&1 || true"
    )
    return _managed_block(inner)


def pre_push_script(root: str) -> str:
    """Opt-in gate (installed only when guard_on_push is on): let the exit code
    propagate so a failing guard blocks the push, but never break on a missing binary."""
    inner = (
        "command -v torsor >/dev/null 2>&1 || exit 0\n"
        f"torsor hooks run pre-push --root {shlex.quote(str(root))}"
    )
    return _managed_block(inner)


def claude_command(root: str) -> str:
    """The command torsor registers for the Claude Code SessionEnd/Stop hook.
    Relative `--root` by default: Claude Code runs hooks with cwd = project root,
    so a relative root avoids baking a machine-specific path into a settings.json
    that may be committed."""
    return f"torsor hooks run session-end --root {shlex.quote(str(root))}"


# SessionStart fires on a fresh start, a --resume, and after every context
# compaction. Injecting on `compact` is what keeps the project digest alive
# across a long session — the documented failure mode is instructions that
# silently vanish after /compact. `clear` is deliberately excluded: the user
# asked for a blank slate.
SESSION_START_MATCHER = "startup|resume|compact"


def claude_start_command(root: str) -> str:
    """The command torsor registers for the Claude Code SessionStart hook."""
    return f"torsor hooks run session-start --root {shlex.quote(str(root))}"


# The edit gate watches the two tools that write source. Bash is deliberately
# not matched: a shell command's effect on files isn't knowable pre-execution,
# and guessing would make the gate noisy exactly where it must be trusted.
EDIT_GATE_MATCHER = "Edit|Write"


def claude_edit_command(root: str) -> str:
    """The command torsor registers for the Claude Code PreToolUse edit gate."""
    return f"torsor hooks run pre-edit --root {shlex.quote(str(root))}"


def _strip_block(text: str) -> tuple[str, bool]:
    """Remove one managed block from `text`. Returns (new_text, found)."""
    if _GIT_START in text and _GIT_END in text:
        pre, rest = text.split(_GIT_START, 1)
        post = rest.split(_GIT_END, 1)[1]
        return pre + post, True
    return text, False


def write_git_hook(hooks_dir, name: str, block: str, *, remove=False) -> Path | None:
    """Idempotently write/refresh a marker-delimited managed block in a git hook,
    preserving any foreign hook body and the exec bit. On remove, strip only the
    block and delete the file if nothing but a shebang remains. Returns the target
    path, or None when there was nothing to do."""
    hooks_dir = Path(hooks_dir)
    target = hooks_dir / name

    if remove:
        if not target.exists():
            return None
        new, found = _strip_block(target.read_text(encoding="utf-8"))
        if not found:
            return None
        if new.strip() in ("", _SHEBANG):
            target.unlink()
            return target
        target.write_text(new.rstrip("\n") + "\n", encoding="utf-8")
        return target

    hooks_dir.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        content = f"{_SHEBANG}\n\n{block}\n"
    else:
        text = target.read_text(encoding="utf-8")
        if _GIT_START in text and _GIT_END in text:
            pre, rest = text.split(_GIT_START, 1)
            post = rest.split(_GIT_END, 1)[1]
            content = pre + block + post
        else:
            body = text if text.startswith("#!") else f"{_SHEBANG}\n{text}"
            content = body.rstrip("\n") + "\n\n" + block + "\n"
    target.write_text(content, encoding="utf-8")
    target.chmod(target.stat().st_mode | 0o111)  # ensure executable
    return target


def _is_torsor_group(group) -> bool:
    """True when every hook in the group is torsor's, i.e. the whole group is
    ours to drop. A group that also holds a foreign hook is NOT ours."""
    entries = _group_hooks(group)
    return bool(entries) and all(_is_torsor_command(h.get("command", "")) for h in entries)


def _group_hooks(group) -> list[dict]:
    if not isinstance(group, dict):
        return []
    return [h for h in (group.get("hooks") or []) if isinstance(h, dict)]


def _without_torsor_hooks(group):
    """The group with torsor's own hook entries removed, or None when nothing
    of the user's is left. Filtering INSIDE the group is the point: dropping the
    whole group deleted foreign hooks that merely shared it with ours."""
    entries = _group_hooks(group)
    kept = [h for h in entries if not _is_torsor_command(h.get("command", ""))]
    if not kept:
        return None
    out = dict(group)
    out["hooks"] = kept
    return out


def merge_settings_hooks(data, *, root: str = ".", on_stop=False, remove=False) -> dict:
    """Pure transform on a parsed .claude/settings.json: drop every torsor-owned
    hook entry (from all events, so --on-stop switches cleanly), then — unless
    removing — append fresh entries to SessionStart, PreToolUse (edit gate) and SessionEnd (or Stop).
    Foreign hooks, foreign events, and all other top-level keys are preserved;
    non-dict input resets."""
    if not isinstance(data, dict):
        data = {}
    out = dict(data)
    hooks_map = dict(out.get("hooks") or {})

    for event in list(hooks_map):
        kept = [g for g in (_without_torsor_hooks(g) for g in (hooks_map.get(event) or []))
                if g is not None]
        if kept:
            hooks_map[event] = kept
        else:
            hooks_map.pop(event, None)

    if not remove:
        event = "Stop" if on_stop else "SessionEnd"
        group = {"hooks": [{"type": "command", "command": claude_command(root)}]}
        hooks_map[event] = list(hooks_map.get(event) or []) + [group]
        start = {
            "matcher": SESSION_START_MATCHER,
            "hooks": [{"type": "command", "command": claude_start_command(root)}],
        }
        hooks_map["SessionStart"] = list(hooks_map.get("SessionStart") or []) + [start]
        gate = {
            "matcher": EDIT_GATE_MATCHER,
            "hooks": [{"type": "command", "command": claude_edit_command(root)}],
        }
        hooks_map["PreToolUse"] = list(hooks_map.get("PreToolUse") or []) + [gate]

    if hooks_map:
        out["hooks"] = hooks_map
    else:
        out.pop("hooks", None)
    return out


def read_settings(path) -> tuple[dict, bool]:
    """Parse a Claude Code settings file. Returns (data, ok). `ok` is False when
    the file exists but is not parseable JSON — Claude Code tolerates comments
    and trailing commas, `json.loads` does not, and a settings file holds the
    user's permissions, env and model. Callers must abort on False rather than
    merge into {}: doing the latter replaced the whole file with torsor's hooks."""
    path = Path(path)
    if not path.exists():
        return {}, True
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, False
    return (loaded if isinstance(loaded, dict) else {}), True


def write_settings(path, data: dict) -> None:
    """Write a settings file atomically, so an interrupted write cannot leave the
    user with a truncated one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".torsor-tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def is_managed_git_hook(text: str) -> bool:
    """True when a hook file carries torsor's managed block."""
    return _GIT_START in text


def settings_events_with_torsor(data) -> list[str]:
    """Claude Code hook events that currently carry a torsor entry."""
    events: list[str] = []
    if not isinstance(data, dict):
        return events
    for event, groups in (data.get("hooks") or {}).items():
        if any(any(_is_torsor_command(h.get("command", "")) for h in _group_hooks(g))
               for g in (groups or [])):
            events.append(event)
    return events


def resolve_hooks_dir(root) -> Path | None:
    """The git hooks directory for `root`, honoring core.hooksPath and worktrees.
    None when `root` is not inside a git repo."""
    try:
        top = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if top.returncode != 0 or not top.stdout.strip():
            return None
        hp = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-path", "hooks"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not hp:
        return None
    hooks_dir = Path(hp)
    if not hooks_dir.is_absolute():
        # git-path is printed relative to the -C directory (root).
        hooks_dir = Path(root) / hooks_dir
    return hooks_dir


def foreign_hook_manager(root) -> str | None:
    """Name of a detected third-party git-hook manager that owns .git/hooks, so
    install can warn instead of fighting it. None when none is detected."""
    root = Path(root)
    if (root / ".husky").is_dir():
        return "husky"
    if (root / ".pre-commit-config.yaml").exists():
        return "pre-commit"
    return None
