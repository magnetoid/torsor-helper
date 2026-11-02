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

# tests/test_coach_lifecycle.py

Symbols in `tests/test_coach_lifecycle.py`.

- L23 `_store(tmp_path, clock=CLOCK)` (function)
- L29 `_decision(store, number, title, body)` (function)
- L38 `test_state_records_when_a_recommendation_was_first_seen(tmp_path)` (function)
- L51 `test_days_open_counts_from_first_seen(tmp_path)` (function)
- L58 `test_days_open_is_zero_for_an_unseen_key(tmp_path)` (function)
- L62 `test_a_corrupt_state_file_still_resets_cleanly(tmp_path)` (function)
- L72 `test_resolve_missing_returns_keys_that_stopped_appearing(tmp_path)` (function)
- L79 `test_a_resolved_key_is_forgotten_so_it_reports_once(tmp_path)` (function)
- L86 `test_a_key_never_shown_is_not_resolved(tmp_path)` (function) — Something that never surfaced was never fixed — claiming otherwise is a lie.
- L93 `test_a_dismissed_key_is_not_resolved(tmp_path)` (function)
- L103 `test_assemble_reports_what_was_fixed(tmp_path)` (function)
- L115 `test_the_resolved_line_appears_once(tmp_path)` (function)
- L126 `test_a_resolved_line_never_resolves_itself(tmp_path)` (function) — The regress: the `resolved` rec is itself shown, then absent next run, so
- L140 `test_recommendations_still_present_are_not_reported_as_fixed(tmp_path)` (function)
- L148 `test_a_recommendation_below_the_limit_is_not_reported_as_fixed(tmp_path)` (function) — Resolution compares against everything computed, not the truncated page —
- L157 `test_session_digest_never_claims_something_was_fixed(tmp_path)` (function) — It runs three index-free checks; a key it does not compute is absent
- L170 `test_an_old_important_recommendation_says_how_long_it_has_been_open(tmp_path)` (function)
- L182 `test_a_fresh_recommendation_says_nothing_about_age(tmp_path)` (function)
- L188 `test_escalation_does_not_reorder_anything(tmp_path, tmp_path_factory)` (function) — It adds information, not position.
