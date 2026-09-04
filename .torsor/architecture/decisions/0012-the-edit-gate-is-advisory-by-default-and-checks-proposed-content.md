---
type: decision
status: accepted
tags:
- adr
links:
- 0009-auto-capture-is-event-driven-and-hook-installers-are-cli-only
created: '2026-09-04T10:30:00'
updated: '2026-09-04T10:30:00'
rules:
- kind: forbid_import
  target: torsor_helper.operations
  scope: src/torsor_helper/hooks.py
  severity: error
  message: "hooks.py is the pure hook core (ADR 0012) — verdict logic (pre_edit, session_start_context) lives in operations, never the reverse"
- kind: forbid_import
  target: torsor_helper.guard
  scope: src/torsor_helper/hooks.py
  severity: error
  message: "hooks.py only templates and merges hook entries (ADR 0012) — it never evaluates rules itself"
---

# ADR 0012: The edit gate is advisory by default and checks proposed content

## Context
The guard caught drift only after it landed: post-commit and pre-push run on files already written, so an agent could violate an ADR, commit, and be told about it later. Claude Code's own docs draw the line — CLAUDE.md is "context, not enforced configuration; to block an action regardless of what Claude decides, use a PreToolUse hook" — and the 2026 governance literature asks for exactly a deterministic gate between the agent and the file. But a gate that blocks by default, or that judges the file *on disk* rather than the edit being proposed, would be wrong twice: it would surprise users (the guard has been advisory since ADR 0009) and it would report drift the edit isn't introducing.

## Decision
`torsor hooks install` registers a PreToolUse hook on `Edit|Write` that runs `torsor hooks run pre-edit`. The core (`operations.pre_edit`) reconstructs the *proposed* file text — a Write's `content`, or the current file with the Edit's `old_string` → `new_string` applied — runs the same per-file rule checks the guard uses, and ratchets against the committed `baseline.json` so only *new* drift is ever reported. Three modes via `automation.guard_on_edit`: `advise` (default) returns the verdict as `additionalContext` and never blocks; `block` denies only when a new violation is `severity: error`; `off` silences it without uninstalling. The gate is read-only (it never writes the file), matches only `Edit|Write` (a Bash command's effect on files isn't knowable pre-execution), ignores writes under `.torsor/` (memory is never architecture drift), and stays silent in the common case so it costs no tokens when there is nothing to say.

## Consequences
Drift is surfaced at the moment of the edit, with the ADR cited, while the default behaviour stays what ADR 0009 promised — advisory, never a surprise block. Because verdicts are ratcheted against the baseline, a legacy violation being edited *near* does not nag; only violations the edit would add do. Cost: each Edit/Write pays one ADR parse + one AST parse (milliseconds), and `block` mode is only as good as the `severity` labels on the rules, so teams that want hard enforcement must mark the rules they mean.
