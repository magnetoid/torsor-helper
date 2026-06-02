---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-02T12:00:00'
updated: '2026-06-02T12:00:00'
rules: []
---

# ADR 0004: Reference edges resolve only the two reliable cases

## Context
v0.2 replaced the cartographer's `blob.count(base)` substring heuristic (which
counted comments, strings, and partial names) with real AST reference edges. A
full call graph would need import-alias tracking plus type inference — fragile
work that an adversarial review measured as needed for ~93% of call sites.

## Decision
`extract_edges` resolves only (a) same-module top-level defs and (b)
`from x import y` aliases mapped to their source module; everything else is
recorded with `resolved_module=None` (degrades gracefully). `Symbol.refs` is the
count of *resolved* references, normalized so a file relpath and a dotted import
target compare equal.

## Consequences
Ref counts are honest and offline-deterministic, replacing a misleading
heuristic. Method calls on non-import receivers (`self.x`, `obj.foo`) resolve to
None, so methods score `refs=0` — accuracy over coverage, by design. A true
cross-file call graph is deferred until resolved-edge coverage is measured on
real repos.
