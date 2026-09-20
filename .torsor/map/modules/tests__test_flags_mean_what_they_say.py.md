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

# tests/test_flags_mean_what_they_say.py

Symbols in `tests/test_flags_mean_what_they_say.py`.

- L20 `_store(tmp_path)` (function)
- L26 `test_auto_index_false_stops_reindexing_an_existing_index(tmp_path)` (function) — It only ever worked on a virgin project: once the DB existed, recall
- L45 `test_verify_reports_staleness_project_wide_on_purpose(tmp_path)` (function) — Not a gap. A staleness finding's source is a NOTE path, while `files`
- L62 `test_a_typo_in_severity_is_rejected_not_silently_widened(tmp_path)` (function) — An unknown threshold mapped to cutoff 0, i.e. "fail on anything" — the
- L71 `test_a_valid_severity_is_still_accepted(tmp_path)` (function)
- L77 `test_mark_and_unmark_together_is_an_error(tmp_path)` (function)
- L83 `test_importance_floors_accept_the_case_a_user_would_write(tmp_path)` (function) — Keyed by Tier.name, so a lowercase key in torsor.toml was ignored and
