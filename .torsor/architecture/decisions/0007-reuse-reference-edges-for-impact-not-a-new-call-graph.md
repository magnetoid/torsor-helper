---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-10T12:05:00'
updated: '2026-06-10T12:05:00'
rules: []
---

# ADR 0007: Impact analysis reuses the v0.2 reference edges (no new call graph)

## Context
Cross-file reasoning failures (regenerating one symbol cascades across callers)
are a core vibe-coding risk. v0.2 already records resolved AST reference edges
(`symbol_edges` / `who_references`). Building a second, heavier call-graph
mechanism for impact analysis would duplicate that and re-introduce the fragile
name-resolution work ADR 0004 deliberately scoped out.

## Decision
`operations.impact(symbol)` resolves the symbol's defining module(s) and queries
the existing edges — read-only, no new index structures. This forced a fix to
`_norm_module`: a `src/`-layout file ("src/proj/core.py") and its import target
("proj.core") must canonicalize equally, so the function now strips a leading
`src.`/`lib.` source-root segment.

## Consequences
Impact is a thin, deterministic read over data the map already builds. The
`_norm_module` fix also retroactively corrects v0.2 cross-module ref counts and
the Mermaid diagram on src-layout repos (previously silently zero). The
normalization is non-injective for pathological duplicate-path-tail repos
(documented); the common single-source-root case is exact.
