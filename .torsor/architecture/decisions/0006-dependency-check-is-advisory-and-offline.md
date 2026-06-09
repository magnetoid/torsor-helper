---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-10T12:00:00'
updated: '2026-06-10T12:00:00'
rules: []
---

# ADR 0006: The dependency check is advisory, offline, and conservative

## Context
LLMs hallucinate non-existent packages (USENIX '25: ~5–21% of AI imports don't
exist), a registerable supply-chain attack. The research named offline
import-existence validation as the missing, locally-performable defense. But a
false positive (flagging a legitimate import) erodes trust fast.

## Decision
`deps.py` resolves each top-level import against the union of stdlib + the
project's own `.venv` (the accurate ground truth, via dist-info
`top_level.txt`/`RECORD` so namespace packages resolve) + first-party repo
modules + declared deps (a fallback, with a dist→import alias table). An import
is flagged only when it matches none. The check is **advisory** (`info`
severity, never a hard CI failure by default) and checks only the top-level name.

## Consequences
Fully offline, deterministic, zero false positives across torsor's own 89
files. It will not catch a hallucinated *submodule* of a real package, and a
no-venv repo relies on the weaker declared-deps fallback — both documented. The
agent must still verify suggestions independently; torsor flags, it does not block.
