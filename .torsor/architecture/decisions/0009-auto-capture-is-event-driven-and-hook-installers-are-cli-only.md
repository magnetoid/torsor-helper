---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-18T21:22:16'
updated: '2026-07-18T21:22:16'
rules:
- kind: forbid_pattern
  target: (?:install|uninstall)_hooks
  scope: src/torsor_helper/server.py
  severity: error
  message: "hook installers are CLI-only (ADR 0009) \u2014 the MCP server must expose\
    \ only the read-only hooks_status"
---

# ADR 0009: Auto-capture is event-driven, and hook installers are CLI-only

## Context
The autonomy layer lets memory capture itself, but torsor's identity is deterministic + offline with NO daemon (README/CHANGELOG state this explicitly). Two failure modes had to be foreclosed: (1) a background watcher/poller would violate the no-daemon rule; (2) exposing install_hooks/uninstall_hooks as MCP tools would let an agent rewrite its own .git/hooks and .claude/settings.json — the same class of footgun as self-update (updater.py is already CLI-only for this reason, per CLAUDE.md). torsor also never calls an LLM, so the auto-handoff must be a deterministic digest, not a generated summary.

## Decision
Auto-capture is strictly event-driven: git and Claude Code are the schedulers; torsor only ever runs `torsor hooks run <event>` once per event and exits. There is no watch/daemon command. The write surface (install_hooks / uninstall_hooks) is CLI-only (`torsor hooks install|uninstall`); the ONLY auto-capture MCP tool is the read-only hooks_status. auto_handoff is a deterministic digest built from git history + the op-log delta + new ADRs + the agent's own active-context/progress — no model call. This is the second documented exception (after updater.py) to the 'every feature is both an MCP tool and a CLI command' convention. Enforced by a guard rule that forbids server.py from referencing the installers, and by test_server_hooks.py asserting install_hooks/uninstall_hooks are not registered tools.

## Consequences
Memory captures itself on the session/commit lifecycle with zero manual handoff/map calls, without a daemon and without an agent being able to self-modify its hook wiring. Cost: auto-handoff can only report what git + the op-log delta can see (op_log is aggregate, not session-scoped — db.py), so it is an honest digest, not a full session replay. The guard rule (forbid_pattern on server.py) makes the CLI-only boundary machine-enforced by `torsor guard --strict`.
