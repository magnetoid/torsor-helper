---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T00:06:46'
updated: '2026-09-21T00:06:46'
---

# src/torsor_helper/render.py

Symbols in `src/torsor_helper/render.py`.

- L22 `caller(entry)` (function) — One row of an impact result: where a reference lives.
- L27 `find_hit(entry)` (function) — One row of a find result — a file path, or a mapped symbol with its site.
- L34 `call_path(path, *, arrow: str='->')` (function) — A connect result: the chain of symbols from source to target.
- L39 `violation(v)` (function) — One drift finding, with the ADR that declared the rule it broke.
- L44 `unknown_import(finding)` (function) — One possible phantom dependency.
- L49 `staleness(finding)` (function) — One piece of memory that no longer matches the code.
- L54 `recommendation(rec, *, arrow: str='→')` (function) — One Coach recommendation, including the key needed to dismiss it.
- L60 `command(entry, *, quote: bool=False)` (function) — One entry from the learned command book.
- L67 `recipe(entry)` (function) — One row of the op-frequency log: a lookup worth routing to a cheap model.
- L73 `recall_hit(hit)` (function) — One recall result as it lands in an agent's context. budget.hit_cost bills
