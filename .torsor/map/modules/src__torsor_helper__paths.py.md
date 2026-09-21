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

# src/torsor_helper/paths.py

Symbols in `src/torsor_helper/paths.py`.

- L6 `contained(root, candidate)` (function) — `candidate` resolved against `root`, or None when it lands outside it.
- L28 `TorsorPaths` (class) — Resolves the .torsor/ directory layout relative to a project root.
- L31 `__init__(self, root: Path | str)` (method)
- L35 `base(self)` (method)
- L39 `config_file(self)` (method)
- L43 `charter(self)` (method)
- L47 `architecture_dir(self)` (method)
- L51 `system_patterns(self)` (method)
- L55 `tech_context(self)` (method)
- L59 `decisions_dir(self)` (method)
- L63 `map_dir(self)` (method)
- L67 `map_overview(self)` (method)
- L71 `active_dir(self)` (method)
- L75 `active_context(self)` (method)
- L79 `progress(self)` (method)
- L83 `memory_dir(self)` (method)
- L87 `journal_dir(self)` (method)
- L91 `insights_dir(self)` (method)
- L95 `llms_txt(self)` (method)
- L99 `commands_file(self)` (method)
- L104 `baseline_file(self)` (method)
- L110 `index_dir(self)` (method)
- L114 `map_dependencies(self)` (method)
- L122 `gitattributes(self)` (method)
- L128 `state_dir(self)` (method)
- L138 `index_db(self)` (method)
- L142 `claude_settings(self)` (method)
- L148 `claude_rules_dir(self)` (method)
- L155 `claude_settings_local(self)` (method)
- L159 `journal_file(self, date_str: str, author: str='')` (method) — `<date>.md`, or `<date>.<author>.md` when journals are partitioned.
