---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-21T01:02:54'
updated: '2026-09-21T01:02:54'
rules: []
---

# src/torsor_helper/operations/prompt_blocks.py

Symbols in `src/torsor_helper/operations/prompt_blocks.py`.

- L25 `_charter_section(body: str, heading: str)` (function) — Lines under `## <heading>` up to the next H2 (empty string if absent).
- L30 `agent_rules(store: Store, config: TorsorConfig, *, max_tokens: int | None=None)` (function) — A compact, token-budgeted digest of the project's standing constraints —
- L60 `_write_managed_block(target, start: str, end: str, content: str)` (function) — Write/refresh a marker-delimited block in `target` (AGENTS.md,
- L78 `write_rules_block(store: Store, config: TorsorConfig, target)` (function)
- L81 `_rule_line(r)` (function)
- L86 `_scope_to_paths_glob(scope: str)` (function) — A guard rule's scope → a Claude Code `paths:` glob (matched relative to
- L100 `write_scoped_rules(store: Store, config: TorsorConfig)` (function) — Export the standing rules as *path-scoped* Claude Code rule files under
- L152 `project_primer(store: Store, config: TorsorConfig, *, max_tokens: int | None=None)` (function) — Token-saver: a budgeted, prompt-time project primer (what this is, how
- L181 `write_primer_block(store: Store, config: TorsorConfig, target, *, max_tokens: int | None=None)` (function)
- L203 `model_policy(store: Store, config: TorsorConfig)` (function) — A prompt-ready model-routing policy: which work runs on the cheap model vs
- L231 `model_policy_json(store: Store, config: TorsorConfig)` (function) — Machine-readable model-routing policy for programmatic routers (any harness,
- L244 `write_model_policy(store: Store, config: TorsorConfig, target)` (function)
