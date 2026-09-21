---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T17:33:16'
updated: '2026-09-21T17:33:16'
rules: []
---

# src/torsor_helper/merge.py

Symbols in `src/torsor_helper/merge.py`.

- L50 `driver_command(root)` (function) — git runs a merge driver from the top of the working tree, which is not
- L71 `attributes_block()` (function)
- L76 `write_attributes(paths)` (function) — Write the managed block into `.torsor/.gitattributes`, keeping any line
- L99 `has_attributes(paths)` (function)
- L108 `driver_registered(root)` (function)
- L112 `register_driver(root)` (function) — Register the map driver in this clone's `.git/config`. Returns False when
- L122 `status(root, paths)` (function) — Everything a caller needs to say which half is missing.
- L137 `_base_relative(path: str)` (function) — git hands the driver a repo-root-relative path; everything else in torsor
- L149 `resolve_map_note(paths, ours: Path, merged_path: str)` (function) — Resolve a `map/**` merge by keeping ours and queueing a regeneration.
- L163 `pending_regeneration(paths)` (function) — Map notes a merge resolved by taking ours, awaiting `torsor map --force`.
- L174 `_write_pending(paths, items: list[str])` (function)
- L185 `clear_pending(paths)` (function) — Called after a full remap, which regenerates every map note anyway.
