---
type: decision
status: superseded
tags:
- adr
links: []
created: '2026-06-02T01:57:25'
updated: '2026-09-04T15:00:00'
rules: []
superseded_by: 0013-python-stays-on-stdlib-ast-other-languages-use-official-tree-sitter-grammar-wheels-never-the-language-pack
---

> **Superseded by [ADR 0013](0013-python-stays-on-stdlib-ast-other-languages-use-official-tree-sitter-grammar-wheels-never-the-language-pack.md):** Python still uses stdlib `ast`, but tree-sitter is no longer rejected outright — the official per-grammar wheels now extract JS/TS/Go, behind an optional `[languages]` extra.

# ADR 0003: Use stdlib ast for the cartographer, not tree-sitter

## Context
tree-sitter-language-pack shipped an unstable, incompatible binding.

## Decision
Extract Python symbols with the stdlib ast module.

## Consequences
Zero-dependency and reliable for Python; multi-language is a planned fast-follow.
