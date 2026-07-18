---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-18T21:35:53'
updated: '2026-07-18T21:35:53'
rules: []
---

# ADR 0010: Staleness detection is high-precision and read-only by default; verify composes existing gates

## Context
2026's #1 open problem in agent memory is staleness — stale notes make agents suggest deprecated patterns. But the failure mode of a staleness detector is false positives: a detector that nags trains the user to ignore the Coach entirely. Dogfooding an early version confirmed this — a naive path-reference detector flagged illustrative example paths in ADR prose and docstrings, and a regex bug matched `.js` inside `.json`. Separately, loop-engineering (removing the human from the turn-by-turn loop) needs a single machine-checkable completion gate, and torsor already has the deterministic pieces (guard, deps) but no aggregator.

## Decision
Staleness detection (coach/staleness.py) ships only DETERMINISTIC, HIGH-PRECISION detectors: dangling wikilinks (deletion is unambiguous) and dead file-path references restricted to inline `code` spans (real refs are backticked; example paths are conventionally "double-quoted"). Fuzzier signals (age/churn decay, symbol-mention heuristics, 'rule violated everywhere') are deliberately omitted — their false-positive rate is too high for a passive surface. Only dangling_link surfaces in the always-on Coach; dead-path findings live only in the explicit `torsor stale` command. The status:stale WRITE is opt-in (`--mark`), reversible (`--unmark`), body-preserving, and never on the MCP default path or in verify. `torsor verify` is a pure AGGREGATOR — it reuses guard_run + check_dependencies + check_staleness (+ an optional recorded test command) and adds no new checking logic, returning a structured verdict {ok, exit_code, checks[], summary} designed as a loop/Stop-hook/CI completion condition. The optional test step reports 'skip' (never 'fail') when no command is recorded, so the default gate stays instant static analysis.

## Consequences
Staleness is trustworthy enough to surface passively without nagging (dogfood: zero false positives on this repo). verify gives agents a one-call, deterministic, offline gate to close autonomous loops. Cost: staleness recall is intentionally lower than a fuzzy detector would give (it won't catch a stale note that names no link/path), and verify's staleness check is repo-wide (a pre-existing dangling link anywhere fails the gate until fixed or the check is narrowed). Both are acceptable trades for precision. New seams: coach/staleness.py, operations.check_staleness/verify, and 'verify'/'check_staleness' added to the cheap model route.
