---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:02'
updated: '2026-09-20T21:54:02'
---

# tests/test_multilang_seams.py

Symbols in `tests/test_multilang_seams.py`.

- L22 `_ts_repo(tmp_path)` (function)
- L34 `test_mixed_python_typescript_and_go_repo_refs_and_methods(tmp_path)` (function)
- L66 `test_connect_walks_a_typescript_call_graph_end_to_end(tmp_path)` (function)
- L77 `test_export_mermaid_draws_a_typescript_module_edge(tmp_path)` (function)
- L89 `test_go_import_hint_survives_a_partial_remap(tmp_path)` (function)
- L123 `test_flat_typescript_layout_resolves_its_own_references(tmp_path)` (function) — Regression: a file living directly at the scan root has no "/" in its
- L149 `test_norm_module_and_norm_path_split_by_what_the_caller_knows()` (function) — The guard rail on the fix above, and why there are two functions.
- L174 `test_partial_remap_re_resolves_a_go_symbol_moved_to_a_sibling_file(tmp_path)` (function) — ADR 0008: a partial map must produce the graph a full remap would.
