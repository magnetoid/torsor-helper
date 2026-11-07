---
type: map
status: derived
tags:
- map
links: []
created: '2026-11-02T02:18:30'
updated: '2026-11-02T02:18:30'
rules: []
---

# tests/test_cleaner.py

Symbols in `tests/test_cleaner.py`.

- L12 `_store(tmp_path)` (function)
- L18 `_mapped(tmp_path, sources)` (function) — A project with `sources` written and fully mapped (map notes + index).
- L27 `test_plan_flags_map_note_whose_source_file_is_gone(tmp_path)` (function)
- L41 `test_plan_counts_index_rows_pointing_at_deleted_files(tmp_path)` (function)
- L57 `_journal(store, date_str, body='## 09:00 · learning\n\nsomething\n')` (function)
- L64 `test_plan_expires_journals_older_than_the_retention_window(tmp_path)` (function)
- L75 `test_retention_of_zero_days_disables_journal_expiry(tmp_path)` (function)
- L84 `test_planning_alone_deletes_nothing(tmp_path)` (function)
- L97 `test_apply_removes_orphaned_map_notes_and_expired_journals(tmp_path)` (function)
- L113 `test_apply_never_touches_source_of_truth_or_code(tmp_path)` (function)
- L130 `test_deep_clean_drops_the_index_but_keeps_the_markdown(tmp_path)` (function)
- L141 `test_package_init_module_is_not_mistaken_for_an_orphan(tmp_path)` (function) — 'pkg/__init__.py' mangles to 'pkg____init__.py.md' — a filename that
