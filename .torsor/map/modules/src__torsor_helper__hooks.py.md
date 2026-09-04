---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T05:04:02'
updated: '2026-09-04T05:04:02'
---

# src/torsor_helper/hooks.py

Symbols in `src/torsor_helper/hooks.py`.

- L20 `_managed_block(inner: str)` (function)
- L24 `post_commit_script(root: str)` (function) — Advisory: refresh the map/snapshot for the just-committed files. A missing
- L34 `pre_push_script(root: str)` (function) — Opt-in gate (installed only when guard_on_push is on): let the exit code
- L44 `claude_command(root: str)` (function) — The command torsor registers for the Claude Code SessionEnd/Stop hook.
- L60 `claude_start_command(root: str)` (function) — The command torsor registers for the Claude Code SessionStart hook.
- L65 `_strip_block(text: str)` (function) — Remove one managed block from `text`. Returns (new_text, found).
- L74 `write_git_hook(hooks_dir, name: str, block: str, *, remove=False)` (function) — Idempotently write/refresh a marker-delimited managed block in a git hook,
- L111 `_is_torsor_group(group)` (function)
- L120 `merge_settings_hooks(data, *, root: str='.', on_stop=False, remove=False)` (function) — Pure transform on a parsed .claude/settings.json: drop every torsor-owned
- L155 `is_managed_git_hook(text: str)` (function) — True when a hook file carries torsor's managed block.
- L160 `settings_events_with_torsor(data)` (function) — Claude Code hook events that currently carry a torsor entry.
- L171 `resolve_hooks_dir(root)` (function) — The git hooks directory for `root`, honoring core.hooksPath and worktrees.
- L196 `foreign_hook_manager(root)` (function) — Name of a detected third-party git-hook manager that owns .git/hooks, so
