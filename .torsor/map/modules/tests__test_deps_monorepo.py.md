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

# tests/test_deps_monorepo.py

Symbols in `tests/test_deps_monorepo.py`.

- L30 `_write(root, rel, text)` (function)
- L37 `_names(root, files)` (function)
- L41 `_monorepo(root)` (function)
- L53 `test_a_nested_app_sees_its_own_manifest(tmp_path)` (function)
- L61 `test_a_nested_app_also_sees_the_root_manifest(tmp_path)` (function) — Node walks up through every node_modules; hoisted root deps are visible.
- L69 `test_a_sibling_apps_dependency_is_not_visible(tmp_path)` (function) — The precision half: resolution is by ancestry, not a repo-wide union of
- L80 `test_a_workspace_package_is_first_party_everywhere(tmp_path)` (function)
- L88 `test_an_empty_scope_is_an_alias_not_a_package(tmp_path)` (function) — npm scopes cannot be empty, so `@/x` is a path alias by definition — no
- L98 `test_tsconfig_paths_are_aliases(tmp_path)` (function)
- L109 `test_a_tsconfig_with_comments_and_trailing_commas_still_parses(tmp_path)` (function) — tsconfig is JSONC. json.loads raises on it, and the real project's
- L131 `test_jsonc(text, expected)` (function) — The first version kept a trailing comma whenever a comment sat between it
- L139 `test_a_url_inside_a_string_is_not_mistaken_for_a_comment(tmp_path)` (function) — Stripping `//` naively would cut "https://..." in half and break the file.
- L150 `test_a_catch_all_alias_resolves_against_the_filesystem(tmp_path)` (function) — `"*": ["src/*"]` (or a bare `baseUrl`) makes any bare specifier possibly
- L163 `test_a_bare_base_url_resolves_like_a_catch_all(tmp_path)` (function)
- L172 `test_an_unparseable_tsconfig_does_not_raise(tmp_path)` (function)
- L180 `test_nested_node_modules_count(tmp_path)` (function)
- L190 `test_manifests_under_node_modules_are_never_read(tmp_path, monkeypatch)` (function) — A real node_modules holds thousands of package.json files; walking into
- L209 `test_a_nested_go_module_sees_its_own_requires(tmp_path)` (function)
- L219 `test_a_go_module_can_import_a_sibling_local_module(tmp_path)` (function)
- L227 `test_resolution_is_built_once_per_call(tmp_path, monkeypatch)` (function) — Per-file manifest discovery must not become a per-file repo walk.
- L253 `test_a_script_can_import_the_module_beside_it(tmp_path)` (function)
- L259 `test_a_module_in_an_ancestor_directory_is_first_party(tmp_path)` (function) — Plugin loaders and test runners put an ancestor on sys.path.
- L267 `test_a_module_in_a_sibling_subtree_is_not_first_party(tmp_path)` (function) — The precision half: ancestry, not "exists anywhere in the repo".
- L283 `test_a_distribution_declared_under_another_name_is_known(tmp_path, dist, module)` (function)
- L289 `test_a_nested_requirements_file_governs_its_own_subtree(tmp_path)` (function)
- L299 `test_a_types_package_makes_its_module_importable(tmp_path)` (function) — `import type { Element } from 'hast'` resolves through @types/hast.
- L313 `test_an_import_guarded_against_absence_is_optional_by_design(tmp_path, guard)` (function) — 57 of the 119 Python findings on the real project were inside a
- L322 `test_a_guard_that_catches_something_else_does_not_count(tmp_path)` (function)
- L327 `test_an_import_in_the_handler_is_not_guarded(tmp_path)` (function) — Only the try body is protected; the fallback in the except clause runs
- L336 `_clean_repo(tmp_path)` (function)
- L349 `test_deps_on_a_clean_tree_says_it_checked_nothing(tmp_path)` (function) — The default is git-changed files, so on a clean checkout the list is
- L365 `test_deps_over_mcp_on_a_clean_tree_says_it_checked_nothing(tmp_path)` (function)
- L384 `test_deps_with_explicit_files_still_finds_them(tmp_path)` (function)
- L394 `test_the_statement_walk_reaches_every_place_an_import_can_live(tmp_path)` (function) — Walking statements instead of every node is what made this 15x faster;
- L445 `test_a_file_whose_imports_are_all_known_is_never_parsed(tmp_path, monkeypatch)` (function) — The parse is the floor — ~9 ms a file on a real project, 21 of its 28
- L466 `test_an_import_word_in_a_docstring_only_costs_a_parse(tmp_path)` (function) — The prefilter may over-approximate — the parse then decides.
- L472 `test_a_projects_invalid_escapes_do_not_reach_the_users_stderr(tmp_path, recwarn)` (function)
