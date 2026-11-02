---
type: map
status: derived
tags:
- map
links: []
created: '2026-11-02T02:18:31'
updated: '2026-11-02T02:18:31'
rules: []
---

# tests/test_edge_storage.py

Symbols in `tests/test_edge_storage.py`.

- L27 `_project(tmp_path)` (function)
- L39 `_stored(store)` (function)
- L47 `test_unresolvable_python_edges_are_not_stored(tmp_path)` (function)
- L56 `test_impact_and_refs_are_unchanged(tmp_path)` (function)
- L69 `test_a_partial_map_still_matches_a_full_one(tmp_path)` (function) — ADR 0008's invariant, with the dropped edges in play: the partial merge
- L81 `test_go_keeps_unresolved_edges_for_its_resolver()` (function)
- L95 `test_the_reported_edge_count_is_what_was_stored(tmp_path)` (function) — `map` said "1 071 508 reference edge(s)" — every name the extractor saw,
- L106 `test_an_index_from_the_old_format_is_remapped_once(tmp_path, monkeypatch)` (function) — Otherwise an existing index keeps its bloat until some source file
- L122 `test_the_format_migration_gives_the_space_back(tmp_path, monkeypatch)` (function) — Dropping 79% of the rows does not shrink the file: SQLite keeps freed
- L146 `test_a_partial_map_that_migrates_first_still_vacuums(tmp_path, monkeypatch)` (function) — The post-commit hook's partial map clears the fingerprint, so if it is
