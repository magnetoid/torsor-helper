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

# tests/test_project_docs.py

Symbols in `tests/test_project_docs.py`.

- L30 `_write(root, rel, text)` (function)
- L37 `_store(tmp_path, sources=DEFAULT)` (function)
- L43 `_rel(store, paths)` (function)
- L49 `test_the_defaults_cover_conventional_docs_but_not_agent_instructions()` (function)
- L55 `test_patterns_are_anchored_at_the_root(tmp_path)` (function) — `README.md` means the project's README, not every README at any depth —
- L67 `test_torsor_s_own_notes_are_never_doc_sources(tmp_path)` (function) — They are indexed already, as the tier they belong to.
- L74 `test_ignored_directories_are_pruned(tmp_path)` (function)
- L83 `test_a_pattern_cannot_reach_outside_the_project(tmp_path, pattern)` (function) — torsor.toml travels in git, so a pattern is untrusted input.
- L92 `test_a_symlink_out_of_the_project_is_not_followed(tmp_path)` (function)
- L102 `test_no_sources_means_no_docs(tmp_path)` (function) — A Store built without config — every existing test — reads nothing extra.
- L112 `test_recall_finds_what_the_project_already_wrote_down(tmp_path)` (function)
- L122 `test_docs_can_be_filtered_by_type(tmp_path)` (function)
- L130 `test_a_doc_that_declares_its_own_type_keeps_it(tmp_path)` (function)
- L137 `test_an_edited_doc_is_reindexed_and_a_deleted_one_disappears(tmp_path)` (function)
- L148 `test_removing_a_pattern_drops_its_docs_from_the_index(tmp_path)` (function)
- L157 `test_the_keyword_fallback_reads_docs_too(tmp_path)` (function) — No index (auto_index off, nothing built): recall reads Markdown directly,
- L168 `test_impact_reports_docs_that_mention_the_symbol(tmp_path)` (function) — The memory-to-symbol link (ADR 0016) extends to the project's own docs.
- L180 `test_torsor_never_writes_a_project_doc(tmp_path)` (function) — The one property that makes reading them in place safe. Everything that
- L202 `test_clean_never_lists_a_project_doc(tmp_path)` (function)
- L213 `test_docs_rank_between_curated_intent_and_derived_notes()` (function) — Authored by the project, so above the map (derived) and working notes;
- L220 `test_importance_floors_accept_the_new_tier(tmp_path)` (function)
- L227 `test_sources_round_trip_through_torsor_toml(tmp_path)` (function)
- L237 `test_stats_counts_project_docs(tmp_path)` (function)
- L251 `test_the_cli_indexes_docs_from_torsor_toml(tmp_path)` (function) — The setting has to reach the Store the adapter builds, or it does nothing.
- L264 `test_the_mcp_server_indexes_docs_from_torsor_toml(tmp_path)` (function)
- L277 `test_db_rows_record_the_docs_tier(tmp_path)` (function)
- L297 `_fresh(tmp_path)` (function)
- L305 `test_bootstrap_never_injects_placeholder_text(tmp_path)` (function)
- L311 `test_bootstrap_includes_a_section_once_it_is_filled_in(tmp_path)` (function)
- L319 `test_the_session_start_digest_on_a_fresh_project_is_short_and_says_why(tmp_path)` (function)
- L328 `test_the_session_start_digest_says_project_docs_are_searchable(tmp_path)` (function)
- L335 `test_recall_never_returns_an_unfilled_template(tmp_path)` (function)
- L341 `test_a_filled_template_is_recalled(tmp_path)` (function)
- L349 `test_get_intent_skips_unfilled_templates(tmp_path)` (function)
- L354 `test_the_coach_and_everything_else_agree_on_what_unfilled_means(tmp_path)` (function) — One definition. The Coach compared stripped text with the seed on its own.
- L365 `test_a_template_indexed_by_an_older_version_is_swept(tmp_path)` (function) — The check has to run before the stat pre-screen, or an unchanged seed that
- L390 `test_rules_never_write_a_placeholder_principle_into_agent_instructions(tmp_path)` (function) — `torsor rules --write` put "_e.g. local-first; Markdown is the source of
- L397 `test_the_primer_never_carries_placeholder_text(tmp_path)` (function) — `primer --write` lands in AGENTS.md / CLAUDE.md, loaded into every session:
- L406 `test_the_primer_includes_a_filled_charter(tmp_path)` (function)
- L412 `test_an_auto_handoff_does_not_copy_placeholders_into_the_journal(tmp_path)` (function)
- L420 `test_mcp_resources_say_a_note_is_unfilled_instead_of_serving_the_seed(tmp_path)` (function)
- L448 `test_is_test_path(path, expected)` (function)
- L454 `_mapped_with_a_test(tmp_path)` (function)
- L467 `test_the_implementation_outranks_the_tests_that_describe_it(tmp_path)` (function)
- L474 `test_asking_about_a_test_still_finds_it(tmp_path)` (function) — Weighted down, not removed.
- L481 `test_the_fresh_project_digest_is_not_cut_mid_word(tmp_path)` (function) — The Coach's share of the session digest was a fixed 8% even when every
