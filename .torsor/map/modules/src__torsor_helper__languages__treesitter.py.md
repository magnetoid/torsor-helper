---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/languages/treesitter.py

Symbols in `src/torsor_helper/languages/treesitter.py`.

- L10 `grammar(name: str)` (function)
- L29 `_parser(name: str)` (function)
- L36 `_query(name: str, source: str)` (function)
- L42 `parse(name: str, text: str)` (function)
- L46 `captures(name: str, node, query: str)` (function)
- L52 `branch_count(name: str, text: str, query: str)` (function) — Number of `@b` captures a branch-node query matches over `text` — the
- L59 `matches(name: str, node, query: str)` (function)
- L65 `text(node)` (function)
- L69 `line(node)` (function)
- L73 `leading_comment(node)` (function) — First line of the comment immediately preceding `node` (JSDoc, `//`, `#`),
- L88 `enclosing(node, types: tuple[str, ...])` (function) — Nearest ancestor whose type is in `types`, or None.
