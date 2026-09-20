---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-20T21:54:01'
updated: '2026-09-20T21:54:01'
---

# src/torsor_helper/operations/prompt_blocks.py

Symbols in `src/torsor_helper/operations/prompt_blocks.py`.

- L25 `_charter_section(body: str, heading: str)` (function) — Lines under `## <heading>` up to the next H2 (empty string if absent).
- L30 `agent_rules(store: Store, config: TorsorConfig, *, max_tokens: int=600)` (function) — A compact, token-budgeted digest of the project's standing constraints —
- L59 `_write_managed_block(target, start: str, end: str, content: str)` (function) — Write/refresh a marker-delimited block in `target` (AGENTS.md,
- L77 `write_rules_block(store: Store, config: TorsorConfig, target)` (function)
- L80 `_rule_line(r)` (function)
- L85 `_scope_to_paths_glob(scope: str)` (function) — A guard rule's fnmatch scope → a Claude Code `paths:` glob (matched
- L97 `write_scoped_rules(store: Store, config: TorsorConfig)` (function) — Export the standing rules as *path-scoped* Claude Code rule files under
- L149 `project_primer(store: Store, config: TorsorConfig, *, max_tokens: int=800)` (function) — Token-saver: a budgeted, prompt-time project primer (what this is, how
- L177 `write_primer_block(store: Store, config: TorsorConfig, target, *, max_tokens: int=800)` (function)
- L199 `model_policy(store: Store, config: TorsorConfig)` (function) — A prompt-ready model-routing policy: which work runs on the cheap model vs
- L227 `model_policy_json(store: Store, config: TorsorConfig)` (function) — Machine-readable model-routing policy for programmatic routers (any harness,
- L240 `write_model_policy(store: Store, config: TorsorConfig, target)` (function)
