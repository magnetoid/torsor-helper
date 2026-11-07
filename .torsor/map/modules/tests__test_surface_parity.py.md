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

# tests/test_surface_parity.py

Symbols in `tests/test_surface_parity.py`.

- L22 `tools(tmp_path)` (function)
- L28 `_cli_options(command: str)` (function) — Option names read off the registered command, not scraped out of rendered
- L50 `test_the_option_reader_can_actually_see_options()` (function) — A helper that silently returns nothing makes every parity assertion below
- L63 `test_a_feature_offers_the_same_controls_on_both_surfaces(tools, tool, cli, shared)` (function)
- L68 `test_map_can_be_scoped_to_paths_from_the_cli()` (function)
- L72 `test_check_dependencies_reports_a_failure_signal(tmp_path)` (function) — It returned prose, so a gate could not tell "clean" from "three phantom
- L90 `test_a_recommendation_can_be_dismissed_over_mcp(tools)` (function)
- L94 `test_the_server_exposes_the_prompts_the_foundation_spec_designed(tmp_path)` (function) — Prompts are how an MCP client renders slash-commands, so the loop steps
- L103 `test_the_architecture_and_map_are_readable_as_resources(tmp_path)` (function)
- L110 `test_a_prompt_on_an_uninitialized_project_says_so(tmp_path)` (function)
