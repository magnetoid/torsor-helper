---
type: map
status: derived
tags:
- map
links: []
created: '2026-11-02T02:18:30'
updated: '2026-11-02T02:18:30'
rules: []
---

# src/torsor_helper/operations/hooks_ops.py

Symbols in `src/torsor_helper/operations/hooks_ops.py`.

- L17 `install_hooks(store, config, *, git=True, claude=True, local=False, on_stop=False)` (function) — Wire git hooks + Claude Code hook entries so capture fires on the lifecycle.
- L78 `uninstall_hooks(store, config, *, local=False)` (function) — Remove only torsor-owned git hooks + Claude Code hook entries.
- L107 `hooks_status(store, config)` (function) — Read-only report of which git hooks + Claude Code events carry a torsor
