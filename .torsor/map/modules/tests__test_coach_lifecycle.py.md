---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T17:40:34'
updated: '2026-09-21T17:40:34'
rules: []
---

# tests/test_coach_lifecycle.py

Symbols in `tests/test_coach_lifecycle.py`.

- L26 `_store(tmp_path, clock=CLOCK)` (function)
- L32 `_decision(store, number, title, body)` (function)
- L41 `test_state_records_when_a_recommendation_was_first_seen(tmp_path)` (function)
- L54 `test_days_open_counts_from_first_seen(tmp_path)` (function)
- L61 `test_days_open_is_zero_for_an_unseen_key(tmp_path)` (function)
- L65 `test_a_corrupt_state_file_still_resets_cleanly(tmp_path)` (function)
- L75 `test_resolve_missing_returns_keys_that_stopped_appearing(tmp_path)` (function)
- L82 `test_a_resolved_key_is_forgotten_so_it_reports_once(tmp_path)` (function)
- L89 `test_a_key_never_shown_is_not_resolved(tmp_path)` (function) — Something that never surfaced was never fixed — claiming otherwise is a lie.
- L96 `test_a_dismissed_key_is_not_resolved(tmp_path)` (function)
- L106 `test_assemble_reports_what_was_fixed(tmp_path)` (function)
- L118 `test_the_resolved_line_appears_once(tmp_path)` (function)
- L129 `test_a_resolved_line_never_resolves_itself(tmp_path)` (function) — The regress: the `resolved` rec is itself shown, then absent next run, so
- L143 `test_recommendations_still_present_are_not_reported_as_fixed(tmp_path)` (function)
- L151 `test_a_recommendation_below_the_limit_is_not_reported_as_fixed(tmp_path)` (function) — Resolution compares against everything computed, not the truncated page —
- L160 `test_session_digest_never_claims_something_was_fixed(tmp_path)` (function) — It runs three index-free checks; a key it does not compute is absent
- L173 `test_an_old_important_recommendation_says_how_long_it_has_been_open(tmp_path)` (function)
- L185 `test_a_fresh_recommendation_says_nothing_about_age(tmp_path)` (function)
- L191 `test_escalation_does_not_reorder_anything(tmp_path, tmp_path_factory)` (function) — It adds information, not position.
- L212 `test_two_decisions_that_disagree_are_flagged(tmp_path)` (function)
- L221 `test_two_decisions_about_different_things_are_not_flagged(tmp_path)` (function)
- L228 `test_two_decisions_that_agree_are_not_flagged(tmp_path)` (function)
- L235 `test_a_superseded_decision_is_not_a_contradiction(tmp_path)` (function) — Supersession is how a decision is *meant* to be reversed.
- L245 `test_an_explicit_supersedes_link_is_not_a_contradiction(tmp_path)` (function)
- L256 `test_non_decisions_are_never_compared(tmp_path)` (function)
- L265 `test_this_repos_own_adrs_contain_no_contradiction()` (function) — The precision test that matters. torsor's own 16 ADRs do not contradict
- L287 `test_polarity(title, expected)` (function)
- L291 `test_contradiction_is_wired_into_the_coach(tmp_path)` (function)
- L299 `test_a_contradiction_can_be_dismissed(tmp_path)` (function)
- L312 `test_the_contradiction_key_is_order_independent(tmp_path)` (function) — Or dismissing it once would not stick the next time the pair is compared
- L322 `test_contradiction_is_advisory(tmp_path)` (function)
