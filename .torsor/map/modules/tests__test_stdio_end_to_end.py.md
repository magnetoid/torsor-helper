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

# tests/test_stdio_end_to_end.py

Symbols in `tests/test_stdio_end_to_end.py`.

- L24 `_Client` (class) — The smallest MCP client that can hold a conversation over stdio.
- L27 `__init__(self, proc)` (method)
- L31 `send(self, method, params=None, *, notify=False)` (method)
- L49 `_entry_point()` (function) — The console script if it is installed, else `python -m torsor_helper`.
- L57 `client(tmp_path)` (function)
- L83 `test_the_server_introduces_itself(client)` (function)
- L89 `test_a_tool_call_round_trips(client)` (function)
- L96 `test_writing_then_reading_memory_over_the_wire(client)` (function)
- L103 `test_prompts_and_resources_are_reachable(client)` (function)
- L111 `test_an_unknown_tool_is_an_error_not_a_crash(client)` (function)
- L117 `test_python_dash_m_is_also_an_entry_point(tmp_path)` (function) — Not everyone has the console script on PATH — a container, a CI step
