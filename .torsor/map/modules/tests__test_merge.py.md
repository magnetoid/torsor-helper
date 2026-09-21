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

# tests/test_merge.py

Symbols in `tests/test_merge.py`.

- L23 `_git(root, *args, check=True)` (function)
- L33 `two_branches(tmp_path)` (function) — A repo with a scaffolded .torsor/ committed on `main`, ready to fork.
- L48 `test_scaffold_writes_gitattributes(tmp_project)` (function)
- L54 `test_gitattributes_is_not_git_ignored(tmp_project)` (function) — It has to travel with the repo — a git-ignored one helps nobody else.
- L60 `test_write_attributes_preserves_foreign_lines(tmp_project)` (function)
- L70 `test_write_attributes_is_idempotent(tmp_project)` (function)
- L80 `test_driver_is_not_registered_by_default(two_branches)` (function)
- L84 `test_register_driver_writes_local_git_config(two_branches)` (function)
- L91 `test_status_reports_the_silent_gap(two_branches)` (function) — Attributes committed, driver unregistered: the case git says nothing about.
- L100 `test_status_outside_a_git_repo_does_not_raise(tmp_project)` (function)
- L106 `test_resolve_map_note_keeps_ours_and_records_it(tmp_project)` (function)
- L116 `test_pending_regeneration_deduplicates(tmp_project)` (function)
- L125 `test_clear_pending_regeneration(tmp_project)` (function)
- L136 `test_journal_frontmatter_does_not_carry_the_wall_clock(tmp_project)` (function) — Two agents starting the same day's journal at different moments must
- L152 `test_journal_entries_still_carry_the_time(tmp_project)` (function)
- L158 `test_journal_updated_is_the_journal_date(tmp_project)` (function)
- L167 `test_partition_date_is_the_default(tmp_project)` (function)
- L172 `test_partition_date_author_suffixes_the_file(two_branches)` (function)
- L177 `test_partition_falls_back_without_a_git_identity(tmp_project, monkeypatch)` (function) — No identity is not an error — it just means no partition to apply.
- L199 `test_author_slug_is_filename_safe(monkeypatch, identity, expected)` (function)
- L206 `test_partitioned_journals_still_expire(two_branches)` (function) — cleaner parses the date out of the filename; a suffix must not hide it.
- L221 `test_config_rejects_an_unknown_partition(tmp_project)` (function)
- L232 `test_config_round_trips_the_partition(tmp_project)` (function)
- L242 `_fork(root, branch, clock_hour, content)` (function)
- L251 `test_concurrent_journals_merge_without_conflict(two_branches)` (function)
- L271 `test_merged_journal_still_parses_as_one_note(two_branches)` (function)
- L288 `test_map_conflict_is_resolved_by_the_driver(two_branches)` (function)
- L308 `test_without_the_driver_the_map_conflicts(two_branches)` (function) — The negative control. If this ever passes, the driver is not what is
