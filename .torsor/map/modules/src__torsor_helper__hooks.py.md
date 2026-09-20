---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/hooks.py

Symbols in `src/torsor_helper/hooks.py`.

- L25 `_is_torsor_command(command)` (function)
- L29 `_managed_block(inner: str)` (function)
- L33 `post_commit_script(root: str)` (function) — Advisory: refresh the map/snapshot for the just-committed files. A missing
- L43 `pre_push_script(root: str)` (function) — Opt-in gate (installed only when guard_on_push is on): let the exit code
- L53 `claude_command(root: str)` (function) — The command torsor registers for the Claude Code SessionEnd/Stop hook.
- L69 `claude_start_command(root: str)` (function) — The command torsor registers for the Claude Code SessionStart hook.
- L80 `claude_edit_command(root: str)` (function) — The command torsor registers for the Claude Code PreToolUse edit gate.
- L85 `_strip_block(text: str)` (function) — Remove one managed block from `text`. Returns (new_text, found).
- L94 `write_git_hook(hooks_dir, name: str, block: str, *, remove=False)` (function) — Idempotently write/refresh a marker-delimited managed block in a git hook,
- L131 `_is_torsor_group(group)` (function) — True when every hook in the group is torsor's, i.e. the whole group is
- L138 `_group_hooks(group)` (function)
- L144 `_without_torsor_hooks(group)` (function) — The group with torsor's own hook entries removed, or None when nothing
- L157 `merge_settings_hooks(data, *, root: str='.', on_stop=False, remove=False)` (function) — Pure transform on a parsed .claude/settings.json: drop every torsor-owned
- L198 `read_settings(path)` (function) — Parse a Claude Code settings file. Returns (data, ok). `ok` is False when
- L214 `write_settings(path, data: dict)` (function) — Write a settings file atomically, so an interrupted write cannot leave the
- L224 `is_managed_git_hook(text: str)` (function) — True when a hook file carries torsor's managed block.
- L229 `settings_events_with_torsor(data)` (function) — Claude Code hook events that currently carry a torsor entry.
- L241 `resolve_hooks_dir(root)` (function) — The git hooks directory for `root`, honoring core.hooksPath and worktrees.
- L266 `foreign_hook_manager(root)` (function) — Name of a detected third-party git-hook manager that owns .git/hooks, so
