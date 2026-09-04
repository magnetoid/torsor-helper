---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T05:04:02'
updated: '2026-09-04T05:04:02'
---

# tests/test_cleaner.py

Symbols in `tests/test_cleaner.py`.

- L12 `_store(tmp_path)` (function)
- L18 `_mapped(tmp_path, sources)` (function) — A project with `sources` written and fully mapped (map notes + index).
- L27 `test_plan_flags_map_note_whose_source_file_is_gone(tmp_path)` (function)
- L41 `test_plan_counts_index_rows_pointing_at_deleted_files(tmp_path)` (function)
- L59 `_journal(store, date_str, body='## 09:00 · learning\n\nsomething\n')` (function)
- L66 `test_plan_expires_journals_older_than_the_retention_window(tmp_path)` (function)
- L77 `test_retention_of_zero_days_disables_journal_expiry(tmp_path)` (function)
- L86 `test_planning_alone_deletes_nothing(tmp_path)` (function)
- L99 `test_apply_removes_orphaned_map_notes_and_expired_journals(tmp_path)` (function)
- L115 `test_apply_mines_insights_before_discarding_a_journal(tmp_path)` (function)
- L126 `test_apply_never_touches_source_of_truth_or_code(tmp_path)` (function)
- L143 `test_deep_clean_drops_the_index_but_keeps_the_markdown(tmp_path)` (function)
- L154 `test_package_init_module_is_not_mistaken_for_an_orphan(tmp_path)` (function) — 'pkg/__init__.py' mangles to 'pkg____init__.py.md' — a filename that
