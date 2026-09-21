---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T17:40:34'
updated: '2026-09-21T17:40:34'
rules: []
---

# src/torsor_helper/coach/contradiction.py

Symbols in `src/torsor_helper/coach/contradiction.py`.

- L49 `polarity(text: str)` (function) — +1 asserts, -1 forbids, 0 says neither.
- L61 `_topic_words(title: str)` (function)
- L67 `_overlap(a: set[str], b: set[str])` (function)
- L72 `_pair_key(a: str, b: str)` (function) — Order-independent, so dismissing a pair sticks whichever way round the
- L79 `_active_decisions(store: Store)` (function)
- L96 `find_contradictions(store: Store)` (function) — Pairs of active decisions that are about the same thing and disagree.
