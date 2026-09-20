---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/operations/decisions.py

Symbols in `src/torsor_helper/operations/decisions.py`.

- L14 `_next_adr_number(store)` (function)
- L23 `_slug(title: str)` (function)
- L27 `_find_adr(store, ref)` (function) — Resolve an ADR by full stem ('0002-foo'), file name, or leading number ('0002'/'2').
- L40 `record_decision(store, title, context, decision, consequences='', rules=None, supersedes=None)` (function)
- L64 `list_practices(store, config, language=None)` (function) — Render the curated best-practice pack(s): one language, or every pack
- L83 `adopt_practices(store, config, language)` (function) — Adopt a best-practice pack: records ONE ADR carrying the pack's
