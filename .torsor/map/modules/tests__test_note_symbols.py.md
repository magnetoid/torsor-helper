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

# tests/test_note_symbols.py

Symbols in `tests/test_note_symbols.py`.

- L24 `_store(tmp_path)` (function)
- L44 `test_extract_symbol_mentions(body, expected)` (function)
- L48 `test_fenced_code_is_not_a_mention()` (function) — A code sample is an illustration, not a claim about a symbol.
- L54 `test_extraction_is_bounded_per_note()` (function) — One pathological note must not flood the table.
- L62 `_indexed(store)` (function)
- L71 `test_reindex_records_mentions(tmp_path)` (function)
- L82 `test_deleting_a_note_drops_its_mentions(tmp_path)` (function)
- L98 `test_editing_a_note_replaces_its_mentions(tmp_path)` (function)
- L115 `test_a_note_indexed_before_the_map_still_links(tmp_path)` (function) — The link is resolved at query time, not at index time.
- L137 `test_impact_reports_the_decisions_that_mention_the_symbol(tmp_path)` (function)
- L153 `test_impact_mentions_are_budgeted(tmp_path)` (function)
- L170 `test_impact_without_an_index_is_still_empty_not_broken(tmp_path)` (function)
- L176 `test_impact_finds_mentions_of_a_symbol_with_no_callers(tmp_path)` (function) — The two halves are independent: a symbol nothing calls can still be the
- L194 `test_recall_can_be_restricted_to_a_symbol(tmp_path)` (function)
- L211 `test_symbol_filter_works_without_an_index(tmp_path)` (function) — The keyword fallback applies the same filter itself — it has no SQL to
- L231 `test_get_intent_shows_what_was_recorded_about_the_topic(tmp_path)` (function) — Asserted on a *journal* note, not a decision: get_intent already lists
- L244 `test_get_intent_without_a_topic_has_no_mentions_section(tmp_path)` (function)
- L253 `test_cli_impact_renders_the_mentions(tmp_path)` (function)
- L271 `test_mcp_recall_accepts_a_symbol_filter(tmp_path)` (function)
- L281 `test_an_index_built_before_mentions_gets_backfilled(tmp_path)` (function) — Without this, the feature returns nothing on every existing project and
- L304 `test_backfill_runs_once(tmp_path)` (function)
