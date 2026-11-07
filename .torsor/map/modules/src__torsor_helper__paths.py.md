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

# src/torsor_helper/paths.py

Symbols in `src/torsor_helper/paths.py`.

- L18 `is_test_path(relpath: str)` (function) — True for a file that is test code by its language's naming convention.
- L23 `contained(root, candidate)` (function) — `candidate` resolved against `root`, or None when it lands outside it.
- L45 `TorsorPaths` (class) — Resolves the .torsor/ directory layout relative to a project root.
- L48 `__init__(self, root: Path | str)` (method)
- L52 `base(self)` (method)
- L56 `config_file(self)` (method)
- L60 `charter(self)` (method)
- L64 `architecture_dir(self)` (method)
- L68 `system_patterns(self)` (method)
- L72 `tech_context(self)` (method)
- L76 `decisions_dir(self)` (method)
- L80 `map_dir(self)` (method)
- L84 `map_overview(self)` (method)
- L88 `active_dir(self)` (method)
- L92 `active_context(self)` (method)
- L96 `progress(self)` (method)
- L100 `memory_dir(self)` (method)
- L104 `journal_dir(self)` (method)
- L108 `insights_dir(self)` (method)
- L112 `commands_file(self)` (method)
- L117 `baseline_file(self)` (method)
- L123 `index_dir(self)` (method)
- L127 `map_dependencies(self)` (method)
- L135 `state_dir(self)` (method)
- L145 `index_db(self)` (method)
- L149 `claude_settings(self)` (method)
- L155 `claude_rules_dir(self)` (method)
- L162 `claude_settings_local(self)` (method)
- L166 `journal_file(self, date_str: str, author: str='')` (method) — `<date>.md`, or `<date>.<author>.md` when journals are partitioned.
