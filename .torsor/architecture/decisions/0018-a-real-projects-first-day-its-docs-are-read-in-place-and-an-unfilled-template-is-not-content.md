---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-09-21T22:00:00'
updated: '2026-09-21T22:00:00'
rules: []
---

# ADR 0018: A real project's first day — its docs are read in place, and an unfilled template is not content

## Context
Everything torsor knew about a project, it knew from `.torsor/`. On its own repo that was fine, because the memory had been written by hand over months. Run on a real 3 200-file project on day one, it showed the cost. There were 2 952 map notes, five seed templates, and nothing else. The project's actual knowledge — README, CONTRIBUTING, 24 design documents in `docs/` — was invisible. So `recall` returned map notes, and test-file map notes first.

The seed templates were worse than empty. The SessionStart hook injected ~283 tokens of "_Describe the product in 2-3 sentences._" into every session, and again after every compaction. `recall` ranked the unfilled System Patterns template first or second for unrelated questions, riding the architecture tier's 1.4 weight. The same placeholder text reached several other outputs:
- `rules --write` put "_e.g. local-first; Markdown is the source of truth._" into the user's `AGENTS.md` as a non-negotiable principle.
- `primer --write` put the whole seed charter there, which the client then loaded into every session.
- `rules --scoped` wrote it into `.claude/rules/torsor/principles.md`.
- Auto-handoff copied "_Unresolved decisions._" into the journal.
- `llms.txt` used the seed as the project summary.
- MCP resources served it verbatim.

## Decision
**Project docs are indexed where they are, read-only.** `memory.sources` holds globs anchored at the project root, and the defaults are the conventional locations: `README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `DESIGN.md`, `docs/`, `doc/`, `adr/` and `rfcs/`. These files are indexed as a new `DOCS` tier with weight 1.3. That puts them above working notes and the derived map, because the project wrote them, and below charter and architecture, because torsor has not curated them as intent. They are re-read when they change and dropped when they are deleted or their pattern is removed. They are never copied into `.torsor/`, which would duplicate them in git and go stale the moment the original was edited. They are never written: every path that writes Markdown walks `.torsor/` only, and a test runs each of those paths and checks the docs byte-for-byte.

Anchoring is deliberate. The guard's scopes follow `.gitignore` semantics, where `README.md` matches at any depth, and that would have pulled in a README per plugin. Patterns cannot reach outside the project (no absolute paths, no `..`, no symlinks out), because torsor.toml travels in git. `CLAUDE.md` and `AGENTS.md` are left out of the defaults: every client already loads its own instructions file, so recalling it again spends tokens on text the agent is already holding.

**An unfilled template is not content.** `templates.is_unfilled(paths, path)` is true while a seeded file is byte-for-byte its seed. There is one definition, and every reader of a seeded note uses it: bootstrap, the session digest, `get_intent`, the indexer, `rules`, `rules --scoped`, the primer, auto-handoff, `llms.txt`, the MCP resources and the Coach. On a fresh project the session digest is now 99 tokens: it says the project docs are searchable and that the charter still needs filling in. `rules --write` with nothing to say writes nothing.

**Map notes for test code are weighted down (×0.5).** Test names are prose about behaviour, like `test_webhook_routes_message`, so lexically they look like answers to questions and outrank the code they test. This was measured on the real project with seven questions. The penalty replaced test notes with the implementation files or with relevant docs in every one — for example `agent/conversation_compression.py` instead of four compression tests. Test notes are weighted down, not removed: a question that names a test still finds it.

## Consequences
On a real project, `recall` answers from the project's own documentation on day one — "how does the gateway route messages" now returns the multi-gateway design doc first. Agent instruction files stop carrying placeholder text, and the session digest stops spending two-thirds of its tokens on it.

Costs. `README.md`, `docs/` and the rest are now part of every existing project's index on upgrade. That is additive and read-only, but recall results change. A large `docs/` costs a one-time embedding pass. Each reindex walks each pattern from its literal prefix, not the whole repo, but a user pattern like `**/*.md` does walk everything. Docs are embedded whole, like notes, so a long one is represented by its opening in the vector leg and by all of it in full-text search. The test-path heuristic knows the conventions of the languages torsor maps and nothing else. A project that keeps tests under an unconventional name gets no correction, and a directory called `spec/` that holds specifications is treated as tests.

No machine rule accompanies this ADR. "Never writes a project doc" and "one definition of unfilled" are behavioural properties, asserted directly in `tests/test_project_docs.py`.
