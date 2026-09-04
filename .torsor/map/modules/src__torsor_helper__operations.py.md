---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T05:04:02'
updated: '2026-09-04T05:04:02'
---

# src/torsor_helper/operations.py

Symbols in `src/torsor_helper/operations.py`.

- L30 `bootstrap_session(store: Store, config: TorsorConfig, *, max_tokens: int | None=None)` (function)
- L63 `session_start_context(store: Store, config: TorsorConfig, *, how: str='startup')` (function) — The digest the Claude Code SessionStart hook injects. Same composition as
- L78 `_recent_journal(store: Store, max_tokens: int, cpt: int)` (function)
- L100 `_embedder_for(config)` (function)
- L107 `_open_index(store, config)` (function) — Return a freshly-synced index connection, or None to use keyword fallback.
- L121 `recall(store: Store, config: TorsorConfig, query: str, limit: int=8)` (function)
- L140 `remember(store: Store, content: str, kind: str='observation', links: list[str] | None=None)` (function)
- L145 `update_active(store: Store, focus: str, progress: str, open_questions: str)` (function)
- L160 `record_handoff(store: Store, summary: str, decisions: str='', open_questions: str='', next_steps: str='')` (function)
- L177 `map_repo(store: Store, config: TorsorConfig, paths: list[str] | None=None, force: bool=False)` (function)
- L236 `export_project(store: Store, config: TorsorConfig)` (function)
- L240 `find_targets(store: Store, config: TorsorConfig, query: str, *, mode: str='fuzzy', limit: int=20, include_files: bool=True, include_symbols: bool=True)` (function) — Fuzzy/literal/regex find over repo files + mapped symbols, frecency-ranked.
- L254 `_charter_section(body: str, heading: str)` (function) — Lines under `## <heading>` up to the next H2 (empty string if absent).
- L260 `agent_rules(store: Store, config: TorsorConfig, *, max_tokens: int=600)` (function) — A compact, token-budgeted digest of the project's standing constraints —
- L290 `_write_managed_block(target, start: str, end: str, content: str)` (function) — Write/refresh a marker-delimited block in `target` (AGENTS.md,
- L311 `write_rules_block(store: Store, config: TorsorConfig, target)` (function)
- L315 `_rule_line(r)` (function)
- L321 `_scope_to_paths_glob(scope: str)` (function) — A guard rule's fnmatch scope → a Claude Code `paths:` glob (matched
- L335 `write_scoped_rules(store: Store, config: TorsorConfig)` (function) — Export the standing rules as *path-scoped* Claude Code rule files under
- L391 `project_primer(store: Store, config: TorsorConfig, *, max_tokens: int=800)` (function) — Token-saver: a budgeted, prompt-time project primer (what this is, how
- L420 `write_primer_block(store: Store, config: TorsorConfig, target, *, max_tokens: int=800)` (function)
- L442 `model_policy(store: Store, config: TorsorConfig)` (function) — A prompt-ready model-routing policy: which work runs on the cheap model vs
- L471 `model_policy_json(store: Store, config: TorsorConfig)` (function) — Machine-readable model-routing policy for programmatic routers (any harness,
- L485 `write_model_policy(store: Store, config: TorsorConfig, target)` (function)
- L494 `list_commands(store: Store)` (function) — The recorded project commands, parsed from .torsor/commands.md.
- L506 `record_command(store: Store, name: str, command: str, note: str='')` (function) — Record/update a named project command so it's never re-derived. Persists to
- L526 `run_command(store: Store, name: str)` (function) — Execute a recorded command (returns CompletedProcess, or None if unknown).
- L540 `_log_op(store: Store, op: str, args: str='')` (function) — Best-effort: record a deterministic-tool call for the 'recipes' view. Never
- L555 `recipes(store: Store, limit: int=10)` (function) — The most-repeated deterministic lookups — what the agent does over and over,
- L567 `impact(store: Store, config: TorsorConfig, symbol: str)` (function) — Blast radius of a symbol: who references it, across files, via the
- L597 `connect(store: Store, config: TorsorConfig, source: str, target: str, *, max_hops: int=12)` (function) — Shortest directed path through the symbol call graph from `source` to
- L655 `get_intent(store: Store, config: TorsorConfig, topic: str | None=None)` (function)
- L694 `_next_adr_number(store)` (function)
- L704 `_slug(title: str)` (function)
- L709 `_find_adr(store, ref)` (function) — Resolve an ADR by full stem ('0002-foo'), file name, or leading number ('0002'/'2').
- L723 `record_decision(store, title, context, decision, consequences='', rules=None, supersedes=None)` (function)
- L754 `list_practices(store, config, language=None)` (function) — Render the curated best-practice pack(s): one language, or every pack
- L772 `adopt_practices(store, config, language)` (function) — Adopt a best-practice pack: records ONE ADR carrying the pack's
- L802 `_rel_to_root(root, toplevel, files)` (function) — Re-anchor git toplevel-relative paths to the torsor root, keeping only
- L821 `_git_changed(root)` (function)
- L846 `_git_changed_in_commit(root, ref='HEAD')` (function) — Source files touched by a single commit (default HEAD) — what the
- L868 `check_drift(store, config, files=None)` (function)
- L875 `new_drift(store, config, files=None)` (function) — Drift beyond the committed baseline — the genuinely-new violations.
- L883 `guard_run(store, config, files=None, *, update_baseline=False, strict=False, severity=None)` (function) — The single guard orchestration both adapters share: check drift, apply
- L900 `check_dependencies(store, config, files=None)` (function) — Flag imports that resolve to no known package (possible slopsquatting).
- L911 `_verify_check(name, ok, status, reasons)` (function)
- L915 `_verify_tests(store)` (function) — Run a recorded `test` (or `verify`) command if one exists; skip — never
- L929 `verify(store, config, files=None, *, severity=None, run_tests=False)` (function) — The single deterministic verification gate: guard (new drift) + deps
- L962 `recommend(store, config, context=None, limit=8)` (function)
- L972 `dismiss_recommendation(store, key)` (function)
- L978 `check_staleness(store, config, *, mark=False, unmark=False)` (function) — Detect memory that contradicts current code — dangling [[wikilinks]] and
- L999 `_stale_notes(store)` (function)
- L1008 `_note_rel(store, path)` (function)
- L1015 `_set_note_status(store, rels: list[str], status: str)` (function) — Rewrite each note's frontmatter `status`, preserving body + other fields
- L1033 `clean(store, config, *, apply: bool=False, deep: bool=False)` (function) — Reclaim derived and expired torsor artefacts. Dry-run by default: without
- L1058 `consolidate(store, config)` (function)
- L1083 `_snapshot_complexity(store)` (function) — Refresh the per-file complexity baseline `coach/trend.find_regressions`
- L1103 `_capture_state_path(store)` (function)
- L1108 `_load_capture_state(store)` (function)
- L1118 `_save_capture_state(store, data: dict)` (function)
- L1126 `_git_out(root, *args)` (function)
- L1136 `_git_head(root)` (function)
- L1140 `_op_totals(store)` (function)
- L1150 `_op_delta(store, snapshot: dict)` (function) — Per-op hit increase since the last snapshot — a best-effort, deterministic
- L1160 `_adrs_between(store, prev: int, cur: int)` (function)
- L1171 `_read_md_section(text: str, header: str)` (function) — Body under a `## header` up to the next `## ` (or EOF). Empty when absent.
- L1181 `_find_file_paths(obj)` (function) — Recursively collect `file_path` string values from a parsed transcript
- L1197 `_transcript_digest(transcript_path)` (function)
- L1219 `auto_handoff(store, config, *, session_id=None, transcript_path=None)` (function) — Write a deterministic end-of-session handoff (no LLM) from git history +
- L1279 `on_commit(store, config)` (function) — Post-commit hook core: partial-map the just-committed source files (the
- L1297 `pre_push(store, config)` (function) — Pre-push hook core: advisory guard. Installed only when guard_on_push is
- L1307 `install_hooks(store, config, *, git=True, claude=True, local=False, on_stop=False)` (function) — Wire git hooks + Claude Code hook entries so capture fires on the lifecycle.
- L1363 `uninstall_hooks(store, config, *, local=False)` (function) — Remove only torsor-owned git hooks + Claude Code hook entries.
- L1390 `hooks_status(store, config)` (function) — Read-only report of which git hooks + Claude Code events carry a torsor
