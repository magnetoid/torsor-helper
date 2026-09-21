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

# tests/test_untested_paths.py

Symbols in `tests/test_untested_paths.py`.

- L25 `_store(tmp_path)` (function)
- L33 `_git_repo(tmp_path)` (function) — pre_push reads git-changed files, so it needs a real repo to have
- L50 `_forbid_requests(store)` (function)
- L57 `test_pre_push_is_a_no_op_when_the_gate_is_off(tmp_path)` (function)
- L71 `test_pre_push_fails_on_new_error_drift_when_enabled(tmp_path)` (function)
- L85 `test_pre_push_does_not_fail_on_baselined_drift(tmp_path)` (function)
- L99 `test_a_missing_transcript_is_not_an_error(tmp_path)` (function)
- L103 `test_a_malformed_transcript_line_is_skipped(tmp_path)` (function)
- L118 `test_an_empty_transcript_yields_nothing(tmp_path)` (function)
- L126 `test_a_bare_scope_becomes_a_recursive_glob()` (function)
- L130 `test_a_directory_scope_is_passed_through()` (function)
- L134 `test_an_empty_scope_falls_back_to_python()` (function)
- L140 `test_check_dependencies_flags_a_phantom_import(tmp_path)` (function)
- L149 `test_check_dependencies_is_quiet_about_the_standard_library(tmp_path)` (function)
- L155 `test_deps_export_find_and_impact_have_a_working_cli(tmp_path)` (function)
- L174 `test_human_bytes_scales_without_rebinding_its_parameter()` (function) — `n /= 1024` turned an int parameter into a float, and because the loop
- L185 `test_commands_add_needs_both_halves(tmp_path)` (function) — Typer hands back (None, None) when --add is absent, and only the name
- L194 `test_mined_insights_are_deduplicated(tmp_path)` (function) — The dedupe read `not (it in seen or seen.add(it))`, which is correct only
