---
type: charter
status: active
tags: [charter]
---

# Project Charter

## What we are building
torsor-helper: a persistent memory + architectural-intent guardrail for AI coding
agents, served over MCP so one install works with every AI coding tool.

## Why it exists
AI coding agents lose the thread over time — context collapse, context myopia, and
loss of architectural intent. torsor-helper gives them a git-versioned, Markdown
"second brain" (the pyramid), a derived semantic index, a symbol map, and a drift
guard, plus a Coach that recommends improvements over time.

## Non-negotiable principles
- Markdown is the source of truth; the index is derived and disposable.
- Local-first; no API key required for the default path.
- Thin MCP/CLI adapters over a tested core (operations/store/guard/cartographer).
- The guard is advisory — it informs, it never blocks or edits code.
