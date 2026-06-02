<div align="center">

# 🧭 torsor-helper

### The memory & coaching layer for AI coding agents.

**Stop re-explaining your project every session. Stop the silent architectural drift.**
One small Python **MCP** server — works with *every* AI coding tool (Claude Code, Codex, Cursor, …).

![CI](https://github.com/magnetoid/torsor-helper/actions/workflows/ci.yml/badge.svg)
![status](https://img.shields.io/badge/status-roadmap%20complete%20(6%2F6)-success)
![tests](https://img.shields.io/badge/tests-155%20passing-brightgreen)
![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![protocol](https://img.shields.io/badge/protocol-MCP-7c3aed)
![local-first](https://img.shields.io/badge/local--first-no%20API%20key-00a3a3)

</div>

---

> **Your AI agent has amnesia.** Every new session starts from zero. Mid-session it forgets the rules you set an hour ago. It rebuilds the helper you already wrote, re-introduces the pattern you explicitly rejected, and quietly drifts from your architecture — with no audit trail. **torsor-helper** is the persistent brain that fixes this, and a **coach** that keeps nudging your project back toward health.

**Contents:** [Why](#-why) · [How it works](#-how-it-works) · [Install](#-install) · [Connect your agent](#-connect-your-agent-claude-code-codex-cursor-) · [Usage](#-usage) · [Team / HTTP mode](#-team--http-mode) · [What's inside](#-whats-inside) · [Status](#-status--roadmap) · [Design](#-design--prior-art)

## 💡 Why

AI coding agents are brilliant in the moment and forgetful over time:

| Failure mode | What it feels like | torsor-helper's answer |
|---|---|---|
| 🧠 **Context Collapse** | New chat = blank slate; long chats drift; the agent loses how files connect. | Pyramidal wiki + `bootstrap_session` + `handoff` |
| 🔭 **Context Myopia** | Optimizes for what's *recent*, not *important*. | Stability-ordered tiers + hybrid recall |
| 🏛️ **Lost Architectural Intent** | Layering/naming rules stop being followed; rejected patterns return. | ADRs-as-rules + `check_drift` |
| ♻️ **Duplication & drift** | Rebuilds code that already exists ([~8× more duplication](https://www.builder.io/m/explainers/vibe-coding-limitations)). | Symbol map + the Coach's `reuse` recs |

Most tools fix *one* of these. **torsor-helper combines four ideas no one else puts together** — a pyramidal wiki, an external semantic memory, a symbol-level repo map, and a drift guard — plus a **Coach** that proactively recommends fixes over time.

<sub>**Why "torsor"?** A *torsor* is a space that looks like a group but has **no fixed origin** — you can only measure *differences* between points. That's exactly drift detection: your architecture is the reference frame, drift is the measured delta.</sub>

## ⚙️ How it works

Your project's memory lives as **plain Markdown you own** — git-versioned, Obsidian-readable, editable by you *and* the agent. A **disposable index** (SQLite FTS5 + local-embedding vectors + a wiki-link graph) is *derived* from those files for instant semantic recall. A single Python **MCP server** serves it all to any agent.

> **One rule:** Markdown is always the source of truth. The index is throwaway — delete it, rebuild it, never fear it.

### 🔺 The pyramid

Five Markdown tiers under `.torsor/`, ordered by **stability** — the broad, stable base loads first; the volatile tip changes every session.

```
                 ╱╲
                ╱T4╲            EPISODIC      memory/       observations · learnings · handoffs · mined insights
               ╱────╲
              ╱  T3  ╲          ACTIVE        active/       current focus · progress · open questions
             ╱────────╲
            ╱    T2    ╲         MAP (derived) map/          repo map · module & symbol summaries
           ╱────────────╲
          ╱      T1      ╲        ARCHITECTURE architecture/ system patterns · tech context · ADRs  ← intent
         ╱────────────────╲
        ╱        T0        ╲       CHARTER      charter.md    what & why · non-negotiable principles  ← most stable
       ╱────────────────────╲
```

## 📦 Install

`torsor-helper` is a small, local-first Python package (Python ≥ 3.11).

**Available now — install the global `torsor` command straight from GitHub (no PyPI needed):**
```bash
uv tool install "git+https://github.com/magnetoid/torsor-helper"
# or:  pipx install "git+https://github.com/magnetoid/torsor-helper"
# with semantic embeddings:  uv tool install "torsor-helper[embeddings] @ git+https://github.com/magnetoid/torsor-helper"
```

**Once published to PyPI** (a GitHub Release away — see [PUBLISHING.md](PUBLISHING.md)):
```bash
uv tool install torsor-helper     # or: pipx install torsor-helper / pip install torsor-helper
uvx torsor-helper --help          # ephemeral, no install
```

**From a local clone (for development):**
```bash
git clone https://github.com/magnetoid/torsor-helper && cd torsor-helper
uv run torsor --help              # uv resolves the env from pyproject automatically
```

> Without the `[embeddings]` extra, recall uses a deterministic offline hashing fallback — everything works with no model download and no API key.

## 🚀 Quick start

```bash
cd your-project
torsor init --write          # scaffold .torsor/ AND write a project .mcp.json
torsor doctor                # sanity-check
```

`torsor init` creates the `.torsor/` pyramid (commit it — it's your project's memory). `--write` drops a `.mcp.json` so MCP clients that read it (**Claude Code** especially) auto-detect torsor-helper. That's it — your agent now has memory.

## 🔌 Connect your agent (Claude Code, Codex, Cursor, …)

torsor-helper is a standard **MCP stdio server** — the command is `torsor mcp`. Point any MCP client at it. `torsor init --client <name>` prints exact, copy-paste config for your tool.

### Claude Code — *zero config*
```bash
torsor init --write                 # writes/merges ./.mcp.json — Claude Code auto-detects it
# or, explicitly:
claude mcp add torsor-helper -- torsor mcp
```

### OpenAI Codex CLI
Add to `~/.codex/config.toml`:
```toml
[mcp_servers.torsor-helper]
command = "torsor"
args = ["mcp"]
```

### Cursor
`torsor init --client cursor` prints the block — paste it into **`.cursor/mcp.json`** (project) or Cursor → *Settings → MCP*:
```json
{ "mcpServers": { "torsor-helper": { "command": "torsor", "args": ["mcp"] } } }
```

### Everything else
The same `mcpServers` block works for **Windsurf, Cline, Roo, Trae, Kiro, Warp, Claude Desktop, Gemini CLI, VS Code/Copilot** — only the config file location differs. Get the exact snippet with:
```bash
torsor init --client windsurf   # or: claude-desktop · vscode · gemini · cline · roo · trae · kiro · warp
```

> **Note:** the config uses `command: "torsor"`, which requires the `torsor` command on your PATH (`uv tool install` / `pipx install`). Running ephemerally instead? Use `"command": "uvx", "args": ["torsor-helper", "mcp"]`.

## 🛠️ Usage

### CLI

| Command | What it does |
|---|---|
| `torsor init [--write] [--client <name>]` | Scaffold `.torsor/`; `--write` emits `.mcp.json`; `--client` prints that client's config |
| `torsor mcp [--http --host --port]` | Run the MCP server (stdio by default; `--http` for a shared service) |
| `torsor doctor` | Verify the project is healthy |
| `torsor index [--full]` | Build/refresh the derived search index |
| `torsor map` | Generate the repository symbol map (`map/`) + symbol inventory |
| `torsor guard [files…] [--strict]` | Flag changes that violate your ADR rules (advisory; `--strict` exits non-zero for CI) |
| `torsor coach [context] [--dismiss <key>]` | Show health + best-practice recommendations |
| `torsor consolidate` | Self-improving pass: mine journal → insight notes, reindex, report duplicates |

### MCP tools (what the agent calls)

| Tool | What it does |
|---|---|
| `bootstrap_session()` | Budgeted summary of the whole pyramid at session start (+ a hygiene digest) |
| `recall(query)` | Hybrid search over memory + wiki (vector + FTS5, fused via RRF) |
| `remember(content)` · `update_active(...)` | Self-editing memory the agent maintains as it works |
| `handoff()` | Structured end-of-session summary → seeds the next session |
| `get_intent(topic?)` · `map_repo()` | Surface the architecture + symbols relevant to a change |
| `record_decision(...)` · `check_drift(...)` | Record ADRs (that become rules); flag changes that violate intent |
| `recommend(context?)` · `consolidate()` | The Coach's recommendations; self-improving maintenance |

### A typical loop
1. **Once:** `torsor init --write`, fill in `charter.md` + `architecture/`, commit `.torsor/`.
2. **Each session:** the agent calls `bootstrap_session()` → gets your charter, architecture, active state, recent memory, and a hygiene nudge or two.
3. **While working:** it `recall()`s prior decisions, `get_intent()` before changes, and `remember()`s what it learns.
4. **Before a commit:** `check_drift()` flags anything that violates your ADR rules.
5. **End of session:** `handoff()` writes a summary the next session resumes from.
6. **Periodically:** `torsor coach` for health + reuse nudges; `torsor consolidate` to distill journal into insights.

### 🩺 The Coach
An **independent advisor that sits beside your coding, never in it.** It watches project health and nudges — *"your `architecture/` is still the template", "12 decisions but 0 rules", "♻️ `format_date()` already exists in `utils/dates.py` — reuse it"* — each with **evidence + a concrete action**, ranked by severity, and **decaying** so it never nags. Pull it (`torsor coach` / `recommend()`), or get it **pushed** as a short digest at session start (silent when healthy). → [Coach design](docs/superpowers/specs/2026-06-01-torsor-coach-design.md)

## 🌐 Team / HTTP mode

Run torsor-helper as a shared service over HTTP (streamable-http) instead of stdio:
```bash
torsor mcp --http --host 0.0.0.0 --port 8000
```
Point HTTP-capable MCP clients at `http://<host>:<port>/mcp`. (stdio remains the default and is best for a single local agent.)

## 🧩 What's inside

A small, layered toolkit — pure core under thin adapters (the agent/CLI never reach past `operations`):

```
src/torsor_helper/
├─ models.py        # Pydantic models: Note, Symbol, Rule, Violation, Recommendation, …
├─ paths.py         # .torsor/ layout            store.py     # Markdown I/O (frontmatter + wikilinks)
├─ templates.py     # seed pyramid               budget.py    # token budgeting
├─ config.py        # torsor.toml                db.py        # SQLite: FTS5 + vectors + edges + symbols
├─ embeddings.py    # FastEmbed | Hashing        indexer.py   # incremental, hash-diff reindex
├─ recall.py        # keyword fallback           search.py    # hybrid RRF retrieval
├─ cartographer.py  # stdlib-ast symbol map      guard.py     # ADR rules → drift detection
├─ coach/           # health · recommender · report · state · mining   (the Coach)
├─ operations.py    # orchestration (the tested core)
├─ server.py        # FastMCP adapter            cli.py       # Typer CLI
```

Everything is **dogfooded**: this repo has its own `.torsor/` with real ADRs whose layering rules `torsor guard` enforces, a `torsor map` of its own 250+ symbols, and a clean `torsor coach` run.

## 📍 Status & roadmap

**Roadmap complete — all six phases shipped (155 tests, lint-clean, dogfooded).**

- [x] **Phase 1 — Foundation** · pyramid scaffold, `init`, MCP server, the five memory tools
- [x] **Phase 2 — Index** · SQLite (FTS5 + wiki-link graph) + local embeddings, incremental indexer, hybrid RRF recall
- [x] **Phase 3 — Map** · stdlib-`ast` cartographer + symbol inventory + `get_intent` / `map_repo`
- [x] **Phase 4 — Guard** · ADRs carry machine-readable rules; deterministic drift detection (`check_drift`)
- [x] **Phase 5 — Consolidation** · `torsor consolidate` mines journal entries into curated insight notes + reports duplicates
- [x] **Phase 6 — Coach** · hygiene + best-practice recommendations (`torsor coach`), pushed at session start
- [x] **HTTP/team transport** · `torsor mcp --http`

**Planned fast-follows:** multi-language map (tree-sitter), a sampling-based *semantic* drift guard, and weaving recs into more tool outputs.

## 🧪 Built with

FastMCP · Typer · Pydantic · PyYAML · SQLite (FTS5) · NumPy · stdlib `ast` — *local-first, no API key required.* Optional `fastembed` extra for semantic embeddings. The repo map is Python-only today (multi-language is planned); the drift guard is deterministic (ADR rules → AST/regex).

## 📚 Design & prior art

Full design + every phase plan live in [`docs/superpowers/`](docs/superpowers/). torsor-helper stands on the shoulders of [Cline Memory Bank](https://docs.cline.bot/prompting/cline-memory-bank), [mem0/OpenMemory](https://mem0.ai/openmemory), [Letta/MemGPT](https://docs.letta.com/), [basic-memory](https://github.com/basicmachines-co/basic-memory), [cognee](https://github.com/topoteretes/cognee), [Aider's repo map](https://aider.chat/docs/repomap.html), [Serena](https://github.com/oraios/serena), and [GitHub spec-kit](https://github.com/github/spec-kit).

## 🤝 Contributing & releasing

`uv run --extra dev pytest` (155 tests) · `uv run --with ruff ruff check src tests`. Releasing: see [PUBLISHING.md](PUBLISHING.md).

## License

[MIT](LICENSE) © Marko Tiosavljevic.

---

<div align="center"><sub>Built with the <a href="https://claude.com/claude-code">Claude Code</a> superpowers workflow — brainstorm → spec → plan → TDD → review.</sub></div>
