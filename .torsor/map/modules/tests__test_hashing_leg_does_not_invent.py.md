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

# tests/test_hashing_leg_does_not_invent.py

Symbols in `tests/test_hashing_leg_does_not_invent.py`.

- L22 `_FakeSemantic` (class) — Identity of a real embedder, vectors of the fake one.
- L29 `_store(tmp_path)` (function)
- L39 `test_a_query_with_no_lexical_match_returns_nothing(tmp_path)` (function)
- L47 `test_a_query_that_does_match_is_unaffected(tmp_path)` (function)
- L56 `test_a_real_embedder_may_still_introduce_a_hit(tmp_path)` (function) — The restriction is on the fallback, not on semantic search.
