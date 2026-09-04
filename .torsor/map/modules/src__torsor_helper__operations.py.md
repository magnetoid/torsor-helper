---
type: map
status: derived
tags:
- map
links: []
created: '2026-09-04T15:38:11'
updated: '2026-09-04T15:38:11'
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
- L238 `_language_counts(modules, root=None)` (function) — Mapped module count per available language, plus — under "unavailable" —
- L254 `_unavailable_language_counts(root)` (function)
- L269 `export_project(store: Store, config: TorsorConfig)` (function)
- L273 `find_targets(store: Store, config: TorsorConfig, query: str, *, mode: str='fuzzy', limit: int=20, include_files: bool=True, include_symbols: bool=True)` (function) — Fuzzy/literal/regex find over repo files + mapped symbols, frecency-ranked.
- L287 `_charter_section(body: str, heading: str)` (function) — Lines under `## <heading>` up to the next H2 (empty string if absent).
- L293 `agent_rules(store: Store, config: TorsorConfig, *, max_tokens: int=600)` (function) — A compact, token-budgeted digest of the project's standing constraints —
- L323 `_write_managed_block(target, start: str, end: str, content: str)` (function) — Write/refresh a marker-delimited block in `target` (AGENTS.md,
- L344 `write_rules_block(store: Store, config: TorsorConfig, target)` (function)
- L348 `_rule_line(r)` (function)
- L354 `_scope_to_paths_glob(scope: str)` (function) — A guard rule's fnmatch scope → a Claude Code `paths:` glob (matched
- L368 `write_scoped_rules(store: Store, config: TorsorConfig)` (function) — Export the standing rules as *path-scoped* Claude Code rule files under
- L424 `project_primer(store: Store, config: TorsorConfig, *, max_tokens: int=800)` (function) — Token-saver: a budgeted, prompt-time project primer (what this is, how
- L453 `write_primer_block(store: Store, config: TorsorConfig, target, *, max_tokens: int=800)` (function)
- L475 `model_policy(store: Store, config: TorsorConfig)` (function) — A prompt-ready model-routing policy: which work runs on the cheap model vs
- L504 `model_policy_json(store: Store, config: TorsorConfig)` (function) — Machine-readable model-routing policy for programmatic routers (any harness,
- L518 `write_model_policy(store: Store, config: TorsorConfig, target)` (function)
- L527 `list_commands(store: Store)` (function) — The recorded project commands, parsed from .torsor/commands.md.
- L539 `record_command(store: Store, name: str, command: str, note: str='')` (function) — Record/update a named project command so it's never re-derived. Persists to
- L559 `run_command(store: Store, name: str)` (function) — Execute a recorded command (returns CompletedProcess, or None if unknown).
- L573 `_log_op(store: Store, op: str, args: str='')` (function) — Best-effort: record a deterministic-tool call for the 'recipes' view. Never
- L588 `recipes(store: Store, limit: int=10)` (function) — The most-repeated deterministic lookups — what the agent does over and over,
- L600 `impact(store: Store, config: TorsorConfig, symbol: str)` (function) — Blast radius of a symbol: who references it, across files, via the
- L630 `connect(store: Store, config: TorsorConfig, source: str, target: str, *, max_hops: int=12)` (function) — Shortest directed path through the symbol call graph from `source` to
- L689 `get_intent(store: Store, config: TorsorConfig, topic: str | None=None)` (function)
- L728 `_next_adr_number(store)` (function)
- L738 `_slug(title: str)` (function)
- L743 `_find_adr(store, ref)` (function) — Resolve an ADR by full stem ('0002-foo'), file name, or leading number ('0002'/'2').
- L757 `record_decision(store, title, context, decision, consequences='', rules=None, supersedes=None)` (function)
- L782 `_source_exts()` (function) — Extensions the default git-changed discovery feeds to guard/deps. Derived
- L793 `list_practices(store, config, language=None)` (function) — Render the curated best-practice pack(s): one language, or every pack
- L811 `adopt_practices(store, config, language)` (function) — Adopt a best-practice pack: records ONE ADR carrying the pack's
- L841 `_rel_to_root(root, toplevel, files)` (function) — Re-anchor git toplevel-relative paths to the torsor root, keeping only
- L861 `_git_changed(root)` (function)
- L886 `_git_changed_in_commit(root, ref='HEAD')` (function) — Source files touched by a single commit (default HEAD) — what the
- L908 `check_drift(store, config, files=None)` (function)
- L915 `new_drift(store, config, files=None)` (function) — Drift beyond the committed baseline — the genuinely-new violations.
- L923 `guard_run(store, config, files=None, *, update_baseline=False, strict=False, severity=None)` (function) — The single guard orchestration both adapters share: check drift, apply
- L940 `check_dependencies(store, config, files=None)` (function) — Flag imports that resolve to no known package (possible slopsquatting).
- L951 `_verify_check(name, ok, status, reasons)` (function)
- L955 `_verify_tests(store)` (function) — Run a recorded `test` (or `verify`) command if one exists; skip — never
- L969 `verify(store, config, files=None, *, severity=None, run_tests=False)` (function) — The single deterministic verification gate: guard (new drift) + deps
- L1002 `recommend(store, config, context=None, limit=8)` (function)
- L1012 `dismiss_recommendation(store, key)` (function)
- L1018 `check_staleness(store, config, *, mark=False, unmark=False)` (function) — Detect memory that contradicts current code — dangling [[wikilinks]] and
- L1039 `_stale_notes(store)` (function)
- L1048 `_note_rel(store, path)` (function)
- L1055 `_set_note_status(store, rels: list[str], status: str)` (function) — Rewrite each note's frontmatter `status`, preserving body + other fields
- L1073 `clean(store, config, *, apply: bool=False, deep: bool=False)` (function) — Reclaim derived and expired torsor artefacts. Dry-run by default: without
- L1098 `consolidate(store, config)` (function)
- L1123 `_snapshot_complexity(store)` (function) — Refresh the per-file complexity baseline `coach/trend.find_regressions`
- L1143 `_capture_state_path(store)` (function)
- L1148 `_load_capture_state(store)` (function)
- L1158 `_save_capture_state(store, data: dict)` (function)
- L1166 `_git_out(root, *args)` (function)
- L1176 `_git_head(root)` (function)
- L1180 `_op_totals(store)` (function)
- L1190 `_op_delta(store, snapshot: dict)` (function) — Per-op hit increase since the last snapshot — a best-effort, deterministic
- L1200 `_adrs_between(store, prev: int, cur: int)` (function)
- L1211 `_read_md_section(text: str, header: str)` (function) — Body under a `## header` up to the next `## ` (or EOF). Empty when absent.
- L1221 `_find_file_paths(obj)` (function) — Recursively collect `file_path` string values from a parsed transcript
- L1237 `_transcript_digest(transcript_path)` (function)
- L1259 `auto_handoff(store, config, *, session_id=None, transcript_path=None)` (function) — Write a deterministic end-of-session handoff (no LLM) from git history +
- L1319 `on_commit(store, config)` (function) — Post-commit hook core: partial-map the just-committed source files (the
- L1337 `pre_push(store, config)` (function) — Pre-push hook core: advisory guard. Installed only when guard_on_push is
- L1347 `_proposed_text(path, tool_name: str, tool_input: dict)` (function) — The file content an Edit/Write *would* produce — reconstructed, never
- L1367 `pre_edit(store, config, tool_name, tool_input)` (function) — PreToolUse edit-gate core: run the ADR rules against the *proposed*
- L1424 `install_hooks(store, config, *, git=True, claude=True, local=False, on_stop=False)` (function) — Wire git hooks + Claude Code hook entries so capture fires on the lifecycle.
- L1480 `uninstall_hooks(store, config, *, local=False)` (function) — Remove only torsor-owned git hooks + Claude Code hook entries.
- L1507 `hooks_status(store, config)` (function) — Read-only report of which git hooks + Claude Code events carry a torsor
