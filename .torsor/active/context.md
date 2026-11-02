---
type: active-context
status: active
tags: [active]
---

# Active Context

## Current focus
Trimming torsor-helper down to a small helper for one developer (ADR 0019): the
team/platform features and the Coach checks that were inert on a solo repo are
removed, and the docs are being rewritten for the smaller surface.

## Recent changes
Removed merge drivers, HTTP transport, `update`, `export`, `find`, `practices`,
`consolidate`, `recipes`, model routing, and five Coach modules. Client registry
cut to six entries.

## Open questions
Migrate to `mcp>=2` (`MCPServer`) next, or make the CLI's heavy imports lazy first?
