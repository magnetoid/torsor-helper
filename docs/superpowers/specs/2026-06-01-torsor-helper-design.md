# torsor-helper — Design Spec

**Date:** 2026-06-01
**Status:** Approved (brainstorming) → pending implementation plan
**Repo:** https://github.com/magnetoid/torsor-helper

## 1. Problem

AI coding agents lose the thread over time. Three documented failure modes:

- **Context Collapse** — *hard collapse* (a new session is a blank slate), *soft collapse* (instructions drift within a long session), and *fragmented collapse* (the agent only sees pasted files and loses how components connect).
- **Context Myopia** — the agent optimizes for what is *recent* over what is *important*; early decisions lose weight ("context rot").
- **Loss of Architectural Intent** — constraints set at the start (layering, naming, design decisions) stop being applied; rejected patterns get re-introduced; architecture drifts with no audit trail.

`torsor-helper` is a Python **MCP server + small CLI** that gives any MCP-capable coding agent a persistent, layered memory and an architectural-intent guardrail. Because it speaks MCP, one install reaches Claude Code, Claude Desktop, Cursor, Windsurf, VS Code/Copilot, Codex, Gemini CLI, Cline, Roo, Trae, Kiro, and Warp.

**Name rationale:** a *torsor* is a space that looks like a group but has no fixed origin — you can only measure *differences* between points, not absolute positions. That is exactly drift detection: architectural intent is the reference frame, and drift is the measured delta from it.

## 2. Landscape & prior art (what we borrow)

| Technique | Best-of-breed reference | What we take |
|---|---|---|
| Pyramidal / hierarchical wiki | Cline Memory Bank; DeepWiki; 3-tier context model | Stability-ordered Markdown tiers, foundation-loaded-first |
| External memory store | mem0/OpenMemory, Letta/MemGPT, basic-memory, cognee, cipher | Self-editing memory tools; Markdown + wikilink knowledge graph; hybrid retrieval; `memify`-style self-improvement |
| Code/architecture awareness | Aider repo map (tree-sitter + PageRank), Serena (LSP/symbol) | Token-budgeted repo map ranked by reference frequency |
| Architectural intent / spec | GitHub spec-kit (ADRs), Anthropic context-engineering | ADRs as the durable intent layer; offload/retrieve/isolate; compaction + handoff |

**The gap we fill:** almost every tool does *one* trick. None actively detect drift away from declared architectural intent. That is the differentiating bet.

## 3. Decisions (from brainstorming)

1. **Build fresh, borrow ideas** — a clean, cohesive Python MCP server with minimal deps, not a wrapper around existing tools.
2. **Markdown + derived index** — Markdown files are the source of truth; a vector/graph index is derived and kept in sync from day one.
3. **Full vision** — including the drift-detection differentiator, built in phases.
4. **Architecture A — Layered "memory OS"** — Markdown substrate + derived SQLite index + MCP tool surface + sampling-based drift guard.

## 4. The pyramid (data model)

Five tiers of plain Markdown, ordered by **stability** (wide stable base loaded first; volatile tip changes constantly):

```
            ╱ Tier 4: EPISODIC ╲          append-only journal of observations,
           ╱  (memory/journal)   ╲         learnings, decisions  → external memory
          ╱──────────────────────╲
         ╱   Tier 3: ACTIVE STATE   ╲      current focus, progress, open questions
        ╱     (active/*.md)           ╲     → beats soft collapse / drift + handoff
       ╱──────────────────────────────╲
      ╱      Tier 2: MAP (derived)       ╲  repo map, module & symbol summaries
     ╱        (map/*.md, regenerated)      ╲ → beats fragmented / multi-file blindness
    ╱────────────────────────────────────────╲
   ╱        Tier 1: ARCHITECTURE                ╲ system-patterns, tech-context, ADRs
  ╱          (architecture/, decisions/)          ╲→ the *intent* the guard enforces
 ╱──────────────────────────────────────────────────╲
╱            Tier 0: CHARTER (most stable)             ╲ brief, product context, principles
────────────────────────────────────────────────────── → beats hard collapse (bootstrap)
```

### On-disk layout (configurable root, default `.torsor/`)

```
.torsor/
  torsor.toml                 # config (embeddings, budgets, root, client)
  charter.md                  # T0  — source of truth for scope & principles
  architecture/
    system-patterns.md        # T1  — patterns, layering, conventions
    tech-context.md           # T1  — stack, versions, constraints
    decisions/
      0001-adopt-mcp.md       # T1  — ADRs (each carries machine-readable rules)
  map/                        # T2  — DERIVED (regenerated), COMMITTED for humans/PR review
    overview.md
    modules/<module>.md
  active/
    context.md                # T3  — current work focus, recent changes
    progress.md               # T3  — done / in-progress / blocked
  memory/
    journal/2026-06-01.md     # T4  — episodic, dated, append-only
    insights/                 # T4  — DERIVED insight notes auto-mined by the Coach (Phase 6)
  .index/                     # DERIVED, git-ignored, disposable
    torsor.db                 # SQLite: vectors + FTS + graph edges
    coach_state.json          # Coach dismissal/decay state (Phase 6)
```

- Every note uses **YAML frontmatter** (`type`, `status`, `tags`, `links`) and **`[[wikilinks]]`** (basic-memory/Obsidian style); wikilinks become graph edges.
- **Markdown is always the source of truth; `.index/` is disposable** and rebuildable at any time.
- `map/` is **committed** (visible in PR review, human-readable) but always regenerable; `.index/` is git-ignored.

## 5. Components (the "small toolkit")

Seven small, single-purpose modules:

| Module | Responsibility | Depends on |
|---|---|---|
| **store** | File I/O, frontmatter + wikilink parsing, content hashing. Owns filesystem truth. | filesystem |
| **indexer** | Incremental embed + index of notes/code into SQLite (`sqlite-vec` + FTS5 + edges). Synced via content hash + `watchfiles`. | store, embeddings |
| **retriever** | Hybrid recall: vector + keyword + graph traversal + recency; returns **token-budgeted** context. | indexer |
| **cartographer** | tree-sitter repo map + PageRank symbol ranking → writes `map/` + symbol edges. | store, tree-sitter |
| **guard** | Drift detection: deterministic ADR rules (AST/import checks) + semantic check via MCP sampling. | store, cartographer, sampling |
| **server** | FastMCP app exposing tools / resources / prompts over stdio + HTTP. | all of the above |
| **cli** | `torsor init / index / map / doctor / mcp / consolidate`; scaffolding + per-client MCP config. | server, store |

Each module has one clear purpose, a typed interface (Pydantic), and is independently testable.

## 6. MCP surface

**Resources** (host attaches as context): `torsor://charter`, `torsor://architecture`, `torsor://active`, `torsor://map/overview`.

**Tools** (model-invoked):

| Tool | Purpose | Failure mode addressed |
|---|---|---|
| `bootstrap_session()` | Budgeted summary of the whole pyramid at session start | hard collapse |
| `get_intent(topic?)` | Fetch architecture/ADRs relevant to an upcoming change | myopia |
| `recall(query, scope?, budget?)` | Hybrid search over memory + wiki + map | hard/soft collapse |
| `remember(content, type, links?)` | Append to episodic memory; auto-index | drift |
| `update_active(focus, progress, open_questions)` | Maintain Tier 3 working state | soft collapse |
| `record_decision(title, context, decision, consequences, rules?)` | Write an ADR that also becomes a guard rule | loss of intent |
| `check_drift(files \| diff)` | Verdict + citation of the intent a change violates | loss of intent |
| `map_repo(paths?)` | (Re)generate the repo map | fragmented collapse |
| `handoff()` | Structured end-of-session summary → next session's bootstrap | soft collapse |
| `recommend(context?, kinds?, limit?)` | Health + best-practice recommendations (Coach, Phase 6) | duplication / inconsistency / rot |

**Prompts** (user slash-commands): `/torsor:onboard`, `/torsor:checkpoint`, `/torsor:review-drift`, `/torsor:coach`.

## 7. Data flow (session lifecycle)

1. **Init** (`torsor init`) — scaffold `.torsor/`, interview (or seed from README) to write `charter.md`, run first `map_repo` + index.
2. **Session start** — host attaches `torsor://` resources, or agent calls `bootstrap_session()` → budgeted pyramid.
3. **During work** — agent calls `get_intent()` before a change, `recall()` for prior context, `remember()` / `record_decision()` to persist. Any `.md` edit → `watchfiles` triggers incremental re-index by content hash.
4. **Before commit/PR** — `check_drift()` compares the change against declared intent; returns violations with citations.
5. **Session end** — `handoff()` writes a structured summary into `active/` + `memory/`; the next session bootstraps with full continuity.

## 8. Drift detection (the differentiator)

Two layers. Intent is the reference frame; drift is the measured delta.

- **Deterministic guards** — ADRs and `system-patterns.md` carry machine-readable rules in frontmatter, e.g.

  ```yaml
  rules:
    - forbid_import: { in_layer: "domain", of: ["requests", "sqlalchemy"] }
    - require: "all handlers subclass BaseHandler"
  ```

  Checked with tree-sitter/AST + the import graph. Fast, deterministic, no LLM.

- **Semantic guard** — for intent that can't be reduced to a rule, the server uses **MCP sampling** to ask the *host's own model* (no API key, no extra cost): given a diff + relevant ADRs/patterns, does this violate declared intent? Returns `{violates, which_intent, explanation, severity}`. If the host does not support sampling, the guard **degrades to deterministic-only + advisory** and never blocks.

- **Self-improvement** (`torsor consolidate`, optional): dedupe near-duplicate memories, reweight graph edges by access frequency, flag stale notes contradicted by newer ADRs, promote frequently-recalled episodic notes into curated wiki (cognee `memify`, kept simple).

## 9. Tech stack

| Concern | Choice | Why |
|---|---|---|
| MCP | **FastMCP** (official Python SDK) | stdio + streamable-HTTP; reaches every MCP client |
| Index DB | **SQLite + `sqlite-vec` + FTS5** | one file, zero server; vectors + keyword + graph together |
| Embeddings | **FastEmbed** (local ONNX) default, pluggable OpenAI/Voyage | local-first, no key required |
| Code parsing | **tree-sitter** (`tree-sitter-language-pack`) | multi-language repo map |
| File watching | **watchfiles** | incremental index sync |
| CLI / models | **Typer** + **Pydantic** | typed tools, clean CLI |
| Packaging | **uv / hatch** → `uvx torsor-helper` & `pipx` | one-command install |

## 10. Error handling

The safety net is that *the index is disposable*:

- Index corruption → `torsor reindex` rebuilds from Markdown (truth is never the DB).
- Sampling unsupported → guard degrades to deterministic + advisory; never blocks the agent.
- Embeddings/model unavailable → recall degrades to FTS5 keyword + structural lookup, with a warning.
- Concurrent edits → atomic writes + content-hash reconciliation on next scan.
- Every context-returning tool enforces a **token budget** — the point is to protect the host window, not flood it.
- All tools return typed (Pydantic) results with a clear error envelope.

## 11. Testing strategy (TDD)

- Unit tests per module with fakes: **deterministic fake embeddings** so ranking tests are stable; **mocked sampling** for the semantic guard.
- tree-sitter fixtures for the cartographer (multi-language).
- Golden-file tests for `bootstrap_session` output and token budgeting.
- Integration tests driving the server via the **FastMCP in-memory test client**.
- Generated MCP config snippets validated per client.

## 12. Platform reach

`torsor init --client <name>` emits ready-to-paste MCP config for: Claude Code, Claude Desktop, Cursor, Windsurf, VS Code/Copilot, Codex, Gemini CLI, Cline, Roo, Trae, Kiro, Warp. stdio transport for local use, HTTP transport for team/shared.

## 13. Phased build order (shippable at each phase)

1. **Foundation** — store + pyramid scaffold + CLI `init` + server with `bootstrap_session`, `remember`, `recall` (FTS-only), `update_active`, `handoff`. *(Beats hard/soft collapse.)*
2. **Index** — SQLite/`sqlite-vec`/FastEmbed, incremental indexer, hybrid retrieval, wikilink graph. *(Real external memory.)*
3. **Map** — tree-sitter cartographer + symbol graph + `get_intent`. *(Beats fragmented collapse / myopia.)*
4. **Guard** — ADRs + deterministic rules + sampling drift check + `record_decision` / `check_drift`. *(The differentiator.)*
5. **Consolidation** — `memify`-style self-improvement + multi-client polish + HTTP/team mode.
6. **Coach** — independent, non-intrusive health & best-practices advisor: hygiene/maturity checks (`stale`/`thin`/`unruled`/`uncharted`) + retrieval-based best-practice recs (`reuse`/`convention`/`decision`/`rejection`/`learning`) + `torsor coach` report + `recommend()` tool + insight auto-mining + decay/escalation. *(Stabilises the project over time; addresses duplication, inconsistency, repeat bugs.)* See [`2026-06-01-torsor-coach-design.md`](2026-06-01-torsor-coach-design.md).

**Hooks for Phase 6 that earlier phases must leave:** Phase 2 — retrieval filterable by frontmatter `type`/`kind`, index stores `type`/`kind`/`signal_strength` + access frequency, add the `memory/insights/` path, register a thin hygiene-only `recommend` tool stub. Phase 3 — expose a queryable symbol inventory + module list. Phase 4 — guard emits findings the Coach surfaces as `convention` recs; ADR `rules:` is the shared rules source.

## 14. Out of scope (YAGNI for now)

- A standalone web dashboard/UI (Markdown + Obsidian already provide a human view).
- Multi-repo / monorepo federation (single repo first).
- Cloud-hosted sync service (local-first; HTTP transport covers team use).
- Editing code on the agent's behalf (Serena already does this; torsor-helper informs, it does not edit source).
