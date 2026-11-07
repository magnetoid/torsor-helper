---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-11-02T00:00:00'
updated: '2026-11-02T00:00:00'
rules: []
---

# ADR 0019: torsor is a small helper for one developer, not a team platform

## Context
By v0.8 the server exposed 29 MCP tools and 38 CLI commands over 11 300 lines. Roughly 40 % of that
was either a team/platform bet (merge drivers for concurrent `.torsor/` writers, an HTTP transport, a
cheap-vs-smart model-routing policy, `llms.txt` export) or something the agents themselves now do
natively: Claude Code, Codex and Cursor all ship session memory, `AGENTS.md` loading, compaction
re-injection and SessionStart/PreCompact/Stop hooks, and Claude Code has LSP-backed navigation.
A tool that is "everything" costs tokens on every tool list, and the Coach checks that needed months
of multi-author history (`coupling`, `trend`, `hubs`) silently returned nothing on a solo repo.

## Decision
torsor-helper is a **small, local-first helper for one developer building fast with an AI agent**.
It owns only what the agents do not: committed, in-repo project memory (charter, ADRs, progress)
that follows `git clone`; a guard that enforces ADR rules as a hook; a small code map with `impact`;
an offline hallucinated-dependency check; the command book; and a Coach limited to health,
staleness, hotspots and phantom deps.

Removed, with their tests: team-memory merge (`merge.py`, `torsor merge *`, `.torsor/.gitattributes`
— **supersedes ADR 0015**), the HTTP transport (stdio only), `torsor update`, `export`/`llms.txt`,
`find`, best-practice packs (`practices`), `consolidate` and journal mining, `recipes` and the
op-frequency log, the model-routing policy, and the Coach modules `coupling`, `trend`, `hubs`,
`contradiction` and `recommender` (ADR 0017's recommendation lifecycle stands; its contradiction
detection is withdrawn). The client registry keeps Claude Code, Cursor, Codex, VS Code, Gemini and a
generic `other`.

## Consequences
- Fewer tools in every session's tool list, and no feature that is inert without a team or a hook.
- A feature comes back only with evidence a solo developer reached for it; "an agent might" is not evidence.
- `numpy` and `tomli-w` are now candidates to drop, and the `mcp<2` pin is the next migration.
