---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-02T01:57:25'
updated: '2026-06-02T01:57:25'
rules:
- kind: forbid_import
  target: torsor_helper.cli
  scope: src/torsor_helper/*.py
  message: nothing should import the CLI entry point
- kind: forbid_import
  target: torsor_helper.server
  scope: src/torsor_helper/operations.py
  message: operations (core) must not import the MCP server adapter
- kind: forbid_import
  target: torsor_helper.operations
  scope: src/torsor_helper/guard.py
  message: guard stays pure (models + store only)
---

# ADR 0002: Adapters depend on core, never the reverse

## Context
Keep server/cli thin and the core testable in isolation.

## Decision
Core modules must not import the cli or server adapters.

## Consequences
The drift guard enforces this via the rules below.
