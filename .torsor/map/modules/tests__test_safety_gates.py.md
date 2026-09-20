---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:02'
updated: '2026-09-20T21:54:02'
---

# tests/test_safety_gates.py

Symbols in `tests/test_safety_gates.py`.

- L18 `_project(tmp_path)` (function)
- L25 `test_the_mcp_verify_tool_cannot_run_recorded_shell_commands(tmp_path)` (function)
- L38 `test_the_cli_can_still_run_them(tmp_path)` (function)
- L47 `no_server(monkeypatch)` (function) — Never let a test actually bind a port — the point is the gate in front.
- L54 `test_http_on_a_non_loopback_host_refuses_without_an_explicit_opt_in(tmp_path, no_server)` (function)
- L62 `test_a_non_loopback_host_serves_once_the_opt_in_is_explicit(tmp_path, no_server)` (function)
- L69 `test_loopback_http_needs_no_opt_in(tmp_path, no_server)` (function)
- L78 `test_clean_apply_deep_refuses_without_yes(tmp_path)` (function)
- L85 `test_clean_apply_without_deep_needs_no_yes(tmp_path)` (function)
- L93 `test_an_unknown_config_key_is_rejected(tmp_path)` (function)
- L100 `test_an_invalid_guard_on_edit_mode_is_rejected(tmp_path)` (function)
- L107 `test_doctor_names_the_offending_key(tmp_path)` (function)
- L115 `test_a_valid_config_still_round_trips(tmp_path)` (function)
