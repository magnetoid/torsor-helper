---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T00:06:46'
updated: '2026-09-21T00:06:46'
---

# tests/test_db.py

Symbols in `tests/test_db.py`.

- L6 `_conn(tmp_path)` (function)
- L10 `test_connect_creates_schema_and_version(tmp_path)` (function)
- L17 `test_pack_stores_the_direction_normalized()` (function)
- L27 `test_pack_leaves_a_zero_vector_alone()` (function)
- L32 `test_upsert_note_and_hashes(tmp_path)` (function)
- L41 `test_fts_search_finds_terms(tmp_path)` (function)
- L52 `test_cosine_search_ranks_by_similarity(tmp_path)` (function)
- L62 `test_edges_and_neighbors(tmp_path)` (function)
- L69 `test_delete_note_removes_everywhere(tmp_path)` (function)
- L79 `test_bump_access(tmp_path)` (function)
- L87 `test_hot_queries_are_index_backed_not_full_scans(tmp_path)` (function) — Each of these ran as a full table scan. who_references is the worst: impact
- L107 `test_connect_skips_the_schema_pass_on_an_already_current_db(tmp_path)` (function) — _create_schema is a write transaction, and every CLI command and every
- L124 `test_connect_still_runs_the_schema_pass_when_the_stamp_is_older(tmp_path)` (function)
