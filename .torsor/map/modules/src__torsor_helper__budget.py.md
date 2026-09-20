---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/budget.py

Symbols in `src/torsor_helper/budget.py`.

- L11 `estimate_tokens(text: str, chars_per_token: int=4)` (function)
- L17 `truncate_to_tokens(text: str, max_tokens: int, chars_per_token: int=4)` (function)
- L35 `hit_cost(title: str, snippet: str, chars_per_token: int=4)` (function) — Token cost of one rendered recall hit — title and framing included.
- L49 `cap_items(items: Sequence[T], max_items: int, *, more: str='')` (function) — Keep the first `max_items` and report what was left out.
