---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T01:13:28'
updated: '2026-09-21T01:13:28'
rules: []
---

# tests/test_embedder_change.py

Symbols in `tests/test_embedder_change.py`.

- L18 `_FakeFastEmbed` (class) — Same vectors, different identity — so only the identity check reacts.
- L25 `_store(tmp_path, notes=5)` (function)
- L35 `test_a_different_embedder_does_not_re_embed_the_corpus(tmp_path)` (function)
- L51 `test_the_good_vectors_are_left_in_place(tmp_path)` (function)
- L64 `test_new_notes_still_get_indexed_for_keyword_search(tmp_path)` (function) — The FTS side must keep working — only embedding is paused.
- L79 `test_returning_to_the_original_embedder_is_also_a_no_op(tmp_path)` (function)
