---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-07-18T20:40:30'
updated: '2026-07-18T20:40:30'
rules: []
---

# ADR 0008: Partial map_repo merges into the graph rather than replacing it wholesale

## Context
The 2026-07-18 audit (docs/audit-report-2026-07-18.md, finding I-4) found that map_repo(paths=[...]) called db.replace_all_symbols/replace_all_edges, which DELETE every module's rows before inserting only the scanned subset. A one-file remap therefore silently wiped the entire symbol/edge index for all other modules. The MCP map_repo tool exposes `paths`, so an agent remapping after editing a single file corrupted the index. A naive merge is also wrong: cartographer computes symbol.refs only over the edges in the current scan, so a subset undercounts cross-module references (rescanning a referenced module alone would drop its ref count to 0).

## Decision
A partial map now MERGES the rescanned modules into the existing graph instead of replacing it. operations.map_repo loads the current symbols/edges (db.load_symbols / db.load_edges), drops the rows for the scanned modules (cartographer.scanned_modules mirrors _scan's module derivation), unions in the freshly-scanned rows, then recomputes refs across the whole union via the extracted cartographer.compute_refs. The result is byte-identical to a pristine full remap (pinned by test_map_repo_partial.test_partial_map_matches_full_map). The rendered map markdown is re-rendered from the full merged symbol set, and the map_fingerprint is still cleared after a partial map so the next full map re-verifies the whole tree. This is a correctness/data-loss fix, NOT true incremental mapping — skip-unchanged-file incremental scanning (audit I-3/I-20) remains a separate fast-follow, likely alongside the tree-sitter multi-language work.

## Consequences
map_repo(paths=[...]) is now safe and produces a complete, correct graph. Cost: a partial map still re-renders and re-indexes the full note set and rewrites all symbol rows (replace_all), so it is not yet cheaper than a full map — it is correct, not fast. compute_refs is now a reusable pure function; scanned_modules and db.load_symbols/load_edges are new seams the incremental-map work can build on.
