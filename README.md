<div align="center">

# 🧭 torsor-helper

### The memory & coaching layer for AI coding agents.

**Stop re-explaining your project every session. Stop the silent architectural drift.**
One small Python MCP server — works with *every* AI coding tool.

![status](https://img.shields.io/badge/status-roadmap%20complete%20(6%2F6)-success)
![tests](https://img.shields.io/badge/tests-146%20passing-brightgreen)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![protocol](https://img.shields.io/badge/protocol-MCP-7c3aed)
![local-first](https://img.shields.io/badge/local--first-no%20API%20key-00a3a3)

</div>

---

> **Your AI agent has amnesia.** Every new session starts from zero. Mid-session it forgets the rules you set an hour ago. It rebuilds the helper you already wrote, re-introduces the pattern you explicitly rejected, and quietly drifts away from your architecture — with no audit trail. `torsor-helper` is the persistent brain that fixes this, and a **coach** that keeps nudging your project back toward health.

## The problem it solves

AI coding agents are brilliant in the moment and forgetful over time. The research backs it up:

| Failure mode | What it feels like |
|---|---|
| 🧠 **Context Collapse** | New chat = blank slate. Long chats drift. The agent only "sees" pasted files and loses how things connect. |
| 🔭 **Context Myopia** | The agent optimizes for what's *recent*, not what's *important*. Early decisions silently lose weight. |
| 🏛️ **Lost Architectural Intent** | Layering, naming, and design rules you set up front stop being followed. Rejected patterns creep back in. |
| ♻️ **Duplication & drift** | AI rebuilds code that already exists ([~8× more duplication](https://www.builder.io/m/explainers/vibe-coding-limitations)) and mixes inconsistent patterns. |

Most tools fix *one* of these. **torsor-helper combines four ideas no one else puts together** — a pyramidal wiki, an external semantic memory, a symbol-level repo map, and a drift guard — plus a **Coach** that proactively recommends fixes over time.

<sub>**Why "torsor"?** A *torsor* is a space that looks like a group but has **no fixed origin** — you can only measure *differences* between points. That's exactly drift detection: your architecture is the reference frame, and drift is the measured delta from it.</sub>

## How it works

Your project's memory lives as **plain Markdown** you own — git-versioned, Obsidian-readable, editable by both you and the agent. A **disposable index** (SQLite + vectors + a wiki-link graph) is *derived* from those files for instant semantic recall. A single Python **MCP server** serves it all to any agent.

> **One rule:** Markdown is always the source of truth. The index is throwaway — delete it, rebuild it, never fear it.

### 🔺 The pyramid

Five Markdown tiers, ordered by **stability** — the broad, stable base loads first; the volatile tip changes every session.

```
                 ╱╲
                ╱T4╲            EPISODIC      memory/      observations, learnings, handoffs
               ╱────╲
              ╱  T3  ╲          ACTIVE        active/      current focus · progress · open Qs
             ╱────────╲
            ╱    T2    ╲        MAP (derived) map/         repo map · module & symbol summaries
           ╱────────────╲
          ╱      T1      ╲      ARCHITECTURE  architecture/ system patterns · tech · ADRs  ← intent
         ╱────────────────╲
        ╱        T0        ╲    CHARTER       charter.md   what & why · non-negotiable principles
       ╱────────────────────╲                                                          ← most stable
```

### 🧰 The MCP toolbelt

| Tool | What it does | Status |
|---|---|:--:|
| `bootstrap_session()` | Hand the agent a budgeted summary of the whole pyramid at session start | ✅ **shipped** |
| `recall(query)` | Hybrid search over memory + wiki — vector + full-text (FTS5) fused via RRF | ✅ **shipped** |
| `remember(content)` · `update_active(...)` | Self-editing memory the agent maintains as it works | ✅ **shipped** |
| `handoff()` | Structured end-of-session summary → seeds the *next* session | ✅ **shipped** |
| `get_intent(topic?)` · `map_repo()` | Surface the architecture/symbols relevant to a change | ✅ **shipped** |
| `record_decision(...)` · `check_drift(...)` | Record ADRs that become rules; flag changes that violate intent | ✅ **shipped** |
| `recommend(context?)` | **The Coach** — health + best-practice recommendations | ✅ **shipped** |
| `consolidate()` | Self-improving maintenance — mine journal entries into insight notes, reindex, report duplicates | ✅ **shipped** |

### 🩺 The Coach *(shipped — `torsor coach`)*

torsor-helper isn't just storage — it's an **independent advisor that sits beside your coding, never in it.** It watches your project's health over time and nudges:

- *"Your active context is 6 sessions stale — run a handoff."*
- *"`architecture/` is still the template — clarify your conventions."*
- *"You've recorded 12 decisions but set 0 rules — formalize the load-bearing ones."*
- *"♻️ You already have `format_date()` in `utils/dates.py` — reuse it."*

It **cites its evidence**, suggests a concrete action, and **decays** so it never nags. → [Coach design](docs/superpowers/specs/2026-06-01-torsor-coach-design.md)

## ⚡ Quick start

```bash
git clone https://github.com/magnetoid/torsor-helper && cd torsor-helper

uv run torsor init --client claude-code   # scaffold .torsor/ + print your MCP config snippet
uv run torsor mcp                          # run the server — your agent connects over stdio
uv run torsor doctor                       # sanity-check the project
```

`init` writes a `.torsor/` folder (your pyramid) and prints a ready-to-paste config for your client. *(PyPI `uvx torsor-helper` is on the roadmap.)*

## 🔌 Works with everything

It's a standard **MCP stdio server**, so any MCP client works. `torsor init --client <name>` emits ready-to-paste config for:

**Claude Code · Claude Desktop · Cursor · Windsurf · VS Code / Copilot · Codex · Gemini CLI · Cline · Roo · Trae · Kiro · Warp**

## 🗺️ Roadmap

- [x] **Phase 1 — Foundation** · pyramid scaffold, `init`, MCP server, the five memory tools *(shipped)*
- [x] **Phase 2 — Index** · SQLite (FTS5 + wiki-link graph) + local embeddings (NumPy cosine), incremental indexer, hybrid RRF recall, `torsor index` *(shipped)*
- [x] **Phase 3 — Map** · `ast` cartographer + symbol inventory + `get_intent` / `map_repo` + `torsor map` *(shipped, 95 tests green)*
- [x] **Phase 4 — Guard** · ADRs carry machine-readable rules; deterministic drift detection (`record_decision` / `check_drift`) + `torsor guard` *(shipped, 113 tests green)*
- [x] **Phase 5 — Consolidation** · `torsor consolidate` mines journal entries into curated insight notes (feeding the Coach) + reindexes + reports duplicates *(shipped)* · HTTP/team transport is a planned fast-follow
- [x] **Phase 6 — Coach** · hygiene checks (`thin`/`stale`/`unruled`/`uncharted`) + best-practice recs (`reuse` + relevant decisions/learnings) via `torsor coach` + `recommend()` *(shipped, 135 tests green)*

## 🛠️ Built with

**Today:** FastMCP · Typer · Pydantic · PyYAML · SQLite (FTS5) · NumPy · stdlib `ast` cartographer — *local-first, no API key required.* The repo map is Python-only today; multi-language (tree-sitter) is planned.
**Optional:** `fastembed` (`pip install torsor-helper[embeddings]`) for semantic embeddings.
**Drift guard** is deterministic (ADR `rules:` → AST import checks + regex); a sampling-based semantic guard is a planned fast-follow.
**Coming:** multi-language map · semantic drift guard · Phase 5 (consolidation) · Phase 6 (the Coach).

## 📚 Design & prior art

Full design lives in [`docs/superpowers/specs/`](docs/superpowers/specs/). torsor-helper stands on the shoulders of [Cline Memory Bank](https://docs.cline.bot/prompting/cline-memory-bank), [mem0/OpenMemory](https://mem0.ai/openmemory), [Letta/MemGPT](https://docs.letta.com/), [basic-memory](https://github.com/basicmachines-co/basic-memory), [cognee](https://github.com/topoteretes/cognee), [Aider's repo map](https://aider.chat/docs/repomap.html), [Serena](https://github.com/oraios/serena), and [GitHub spec-kit](https://github.com/github/spec-kit) — combining the best ideas from each into one small toolkit.

## License

TBD (MIT planned).

---

<div align="center"><sub>Built with the <a href="https://claude.com/claude-code">Claude Code</a> superpowers workflow — brainstorm → spec → plan → TDD.</sub></div>
