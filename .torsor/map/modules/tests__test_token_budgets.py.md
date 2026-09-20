---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:02'
updated: '2026-09-20T21:54:02'
---

# tests/test_token_budgets.py

Symbols in `tests/test_token_budgets.py`.

- L22 `_store(tmp_path)` (function)
- L28 `_fat(store, words=4000)` (function) — Fill every seeded note past any plausible budget.
- L40 `_tokens(text, config)` (function)
- L46 `test_cap_items_keeps_everything_when_it_fits()` (function)
- L52 `test_cap_items_reports_how_many_it_dropped()` (function)
- L58 `test_cap_items_tail_carries_the_caller_hint()` (function)
- L63 `test_cap_items_treats_a_non_positive_cap_as_no_cap()` (function)
- L70 `test_session_start_context_never_exceeds_its_budget(tmp_path)` (function)
- L81 `test_bootstrap_session_never_exceeds_its_budget(tmp_path)` (function)
- L89 `test_bootstrap_coach_digest_is_inside_the_budget_not_appended_after_it(tmp_path)` (function)
- L104 `test_get_intent_respects_its_own_budget(tmp_path)` (function)
- L112 `test_get_intent_caps_the_decision_list_and_says_how_many_it_hid(tmp_path)` (function)
- L131 `test_impact_caps_callers_but_still_reports_the_true_total(tmp_path)` (function)
- L151 `test_impact_limit_defaults_to_the_configured_cap(tmp_path)` (function)
- L172 `test_list_practices_respects_its_budget(tmp_path)` (function)
- L186 `test_verify_caps_reasons_per_check_but_keeps_the_true_count(tmp_path)` (function)
- L208 `_render_recall(result)` (function) — Exactly how server.py renders a RecallResult into the agent's context.
- L213 `test_recall_budget_covers_what_actually_lands_in_context(tmp_path)` (function)
- L231 `test_recall_reported_total_matches_what_it_charged(tmp_path)` (function)
