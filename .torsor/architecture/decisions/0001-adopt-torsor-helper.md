---
type: decision
status: accepted
tags: [adr]
links: []
rules: []
---

# ADR 0001: Adopt torsor-helper

## Context
This project uses torsor-helper to persist architectural intent and memory.

## Decision
Markdown under `.torsor/` is the source of truth; the index is derived and disposable.

## Consequences
Memory is git-versioned and human-editable. Future ADRs may add machine-readable
`rules:` in frontmatter that the drift guard enforces (Phase 4).
