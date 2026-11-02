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

# tests/test_hotspot_pruning.py

Symbols in `tests/test_hotspot_pruning.py`.

- L35 `test_the_bound_is_never_below_the_real_complexity(tmp_path, name, text)` (function)
- L46 `test_the_bound_holds_on_every_real_file_in_this_repo()` (function) — Snippets prove the idea; this proves it on code nobody wrote to pass.
- L61 `test_an_unknown_language_is_never_pruned(tmp_path)` (function) — The bound is only valid for languages whose branch tokens it knows.
- L67 `test_an_unavailable_language_is_never_pruned(tmp_path, monkeypatch)` (function)
- L72 `_repo_with_history(tmp_path, files)` (function)
- L87 `_branchy(n)` (function)
- L91 `test_pruned_hotspots_equal_brute_force(tmp_path)` (function) — Exact, not approximate: the same files in the same order as scoring
- L111 `test_pruning_actually_skips_files(tmp_path, monkeypatch)` (function)
- L126 `test_churn_asks_for_the_extension_list_once(tmp_path, monkeypatch)` (function) — It was called once per line of `git log` output — every line re-checked
- L146 `_mapped(tmp_path)` (function)
- L162 `_uncharted(store)` (function) — Through ops.recommend, the way both adapters reach it: assemble() on its
- L171 `test_a_freshly_mapped_repo_has_nothing_uncharted(tmp_path)` (function)
- L175 `test_a_change_after_mapping_says_the_map_is_out_of_date(tmp_path)` (function)
- L183 `test_no_map_at_all_still_says_so(tmp_path)` (function)
