---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/languages/modules.py

Symbols in `src/torsor_helper/languages/modules.py`.

- L9 `strip_suffix(module: str)` (function) — `.py` comes off any key. A NON-Python suffix comes off only a path-shaped
- L24 `_canonicalize(stripped: str, original: str)` (function) — Shared tail of norm_module/norm_path: collapse a JS/TS `index` file to its
- L37 `norm_module(module: str)` (function) — Canonical key for a module reference that MAY be a dotted import target.
- L47 `norm_path(relpath: str)` (function) — Canonical key for a FILE PATH — the caller knows it is one, so a
