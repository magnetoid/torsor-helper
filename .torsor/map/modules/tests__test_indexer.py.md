---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T01:02:54'
updated: '2026-09-21T01:02:54'
rules: []
---

# tests/test_indexer.py

Symbols in `tests/test_indexer.py`.

- L13 `_setup(tmp_path)` (function)
- L20 `test_reindex_indexes_all_notes(tmp_path)` (function)
- L28 `test_reindex_rebuilds_when_embedder_dim_changes(tmp_path)` (function)
- L41 `test_reindex_is_incremental(tmp_path)` (function)
- L51 `test_reindex_deletes_removed_notes(tmp_path)` (function)
- L60 `test_reindex_records_type_and_kind(tmp_path)` (function)
- L70 `test_reindex_survives_malformed_and_undecodable_notes(tmp_path)` (function)
- L85 `test_reindex_full_when_index_schema_changes(tmp_path)` (function)
- L95 `test_wikilink_edges_resolve_regardless_of_index_order(tmp_path)` (function)
- L107 `test_wikilink_edges_heal_when_target_created_later(tmp_path)` (function)
- L120 `test_slug_resolution_is_literal_not_like_pattern(tmp_path)` (function)
- L127 `test_connect_enables_wal_and_busy_timeout(tmp_path)` (function)
- L133 `test_reindex_skips_unchanged_notes_without_reading(tmp_path, monkeypatch)` (function)
- L144 `test_reindex_rewrite_with_same_content_skips_reembed(tmp_path)` (function)
- L158 `test_a_ddl_only_schema_bump_does_not_re_embed_everything(tmp_path, monkeypatch)` (function) — Adding a secondary index or a lookup table says nothing about whether a
- L171 `test_a_format_bump_does_re_embed(tmp_path, monkeypatch)` (function)
