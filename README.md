# torsor-mem

**A persistent memory + architectural-intent guardrail for AI coding agents — over MCP, for every platform.**

> ⚠️ **Status: design phase.** This repo currently contains the design spec
> ([`docs/superpowers/specs/2026-06-01-torsor-mem-design.md`](docs/superpowers/specs/2026-06-01-torsor-mem-design.md)).
> Implementation is phased (see [Roadmap](#roadmap)). Usage examples below describe the **planned** interface.

---

## Why

AI coding agents lose the thread over time. `torsor-mem` targets three documented failure modes:

| Problem | What it looks like |
|---|---|
| **Context Collapse** | New session = blank slate (*hard*); instructions drift mid-session (*soft*); agent only sees pasted files and loses how things connect (*fragmented*). |
| **Context Myopia** | The agent optimizes for what's *recent* over what's *important*; early decisions lose weight. |
| **Loss of Architectural Intent** | Constraints set at the start (layering, naming, design decisions) stop being applied; rejected patterns creep back; architecture drifts with no audit trail. |

Most tools fix *one* of these. `torsor-mem` combines a **pyramidal wiki**, an **external memory** with hybrid retrieval, a **repo map**, and — the differentiator — **drift detection against your declared architectural intent**.

> **Why "torsor"?** A *torsor* is a space that looks like a group but has no fixed origin — you can only measure *differences* between points. That's drift detection: your architecture is the reference frame, and drift is the measured delta from it.

## How it works

Memory lives as **plain Markdown** (git-versioned, Obsidian-readable, human- and agent-editable). A disposable **SQLite index** (`sqlite-vec` + FTS5 + a graph of wikilinks/symbols) is derived from those files for semantic + relational recall. A single Python **MCP server** exposes it to any agent.

### The pyramid

Five Markdown tiers, ordered by stability — the stable base loads first, the volatile tip changes constantly:

```
  Tier 4  EPISODIC      memory/journal/   append-only observations & learnings
  Tier 3  ACTIVE STATE  active/           current focus, progress, open questions
  Tier 2  MAP (derived) map/              repo map, module & symbol summaries
  Tier 1  ARCHITECTURE  architecture/     system patterns, tech context, ADRs  <- the intent
  Tier 0  CHARTER       charter.md        brief, product context, principles   <- most stable
```

### MCP tools

| Tool | Purpose |
|---|---|
| `bootstrap_session()` | Budgeted summary of the whole pyramid at session start |
| `get_intent(topic?)` | Fetch the architecture/ADRs relevant to an upcoming change |
| `recall(query)` | Hybrid search over memory + wiki + map |
| `remember(content)` / `update_active(...)` | Self-editing memory |
| `record_decision(...)` | Write an ADR that also becomes a guard rule |
| `check_drift(files\|diff)` | Verdict + citation of the intent a change violates |
| `map_repo()` | (Re)generate the repo map |
| `handoff()` | Structured end-of-session summary → next session's bootstrap |

## Works with (planned)

MCP is the lingua franca, so one install reaches **Claude Code, Claude Desktop, Cursor, Windsurf, VS Code / Copilot, Codex, Gemini CLI, Cline, Roo, Trae, Kiro, and Warp.**

## Quick start (planned)

```bash
# install + scaffold the pyramid in your repo
uvx torsor-mem init --client claude-code

# run the MCP server (your agent connects over stdio)
torsor mcp
```

`init` writes a `.torsor/` directory and prints the MCP config snippet for your chosen client.

## Tech stack

FastMCP · SQLite + `sqlite-vec` + FTS5 · FastEmbed (local embeddings) · tree-sitter · watchfiles · Typer · Pydantic. Local-first, minimal dependencies, no API key required.

## Roadmap

- [ ] **Phase 1 — Foundation:** pyramid scaffold, `init`, MCP server with `bootstrap_session` / `remember` / `recall` (FTS) / `update_active` / `handoff`
- [ ] **Phase 2 — Index:** `sqlite-vec` + FastEmbed, incremental indexer, hybrid retrieval, wikilink graph
- [ ] **Phase 3 — Map:** tree-sitter cartographer + symbol graph + `get_intent`
- [ ] **Phase 4 — Guard:** ADRs + deterministic rules + sampling-based drift check + `check_drift`
- [ ] **Phase 5 — Consolidation:** self-improving memory + multi-client polish + HTTP/team mode

## Design & prior art

Full design: [`docs/superpowers/specs/2026-06-01-torsor-mem-design.md`](docs/superpowers/specs/2026-06-01-torsor-mem-design.md). It builds on ideas from Cline Memory Bank, mem0/OpenMemory, Letta/MemGPT, basic-memory, cognee, Aider's repo map, Serena, and GitHub spec-kit.

## License

TBD.
