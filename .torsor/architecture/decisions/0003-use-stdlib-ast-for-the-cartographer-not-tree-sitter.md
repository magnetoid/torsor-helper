---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-02T01:57:25'
updated: '2026-06-02T01:57:25'
rules: []
---

# ADR 0003: Use stdlib ast for the cartographer, not tree-sitter

## Context
tree-sitter-language-pack shipped an unstable, incompatible binding.

## Decision
Extract Python symbols with the stdlib ast module.

## Consequences
Zero-dependency and reliable for Python; multi-language is a planned fast-follow.
