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

# src/torsor_helper/operations/prompt_blocks.py

Symbols in `src/torsor_helper/operations/prompt_blocks.py`.

- L24 `_charter_section(body: str, heading: str)` (function) — Lines under `## <heading>` up to the next H2 (empty string if absent).
- L29 `agent_rules(store: Store, config: TorsorConfig, *, max_tokens: int | None=None)` (function) — A compact, token-budgeted digest of the project's standing constraints —
- L61 `_write_managed_block(target, start: str, end: str, content: str)` (function) — Write/refresh a marker-delimited block in `target` (AGENTS.md,
- L79 `write_rules_block(store: Store, config: TorsorConfig, target)` (function) — Write the rules digest into `target` as a managed block. None when there
- L94 `_rule_line(r)` (function)
- L99 `_scope_to_paths_glob(scope: str)` (function) — A guard rule's scope → a Claude Code `paths:` glob (matched relative to
- L113 `write_scoped_rules(store: Store, config: TorsorConfig)` (function) — Export the standing rules as *path-scoped* Claude Code rule files under
- L167 `project_primer(store: Store, config: TorsorConfig, *, max_tokens: int | None=None)` (function) — Token-saver: a budgeted, prompt-time project primer (what this is, how
- L200 `write_primer_block(store: Store, config: TorsorConfig, target, *, max_tokens: int | None=None)` (function)
