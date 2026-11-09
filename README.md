<div align="center">

# 🧭 torsor-helper

### Project memory · guardrails · a coach — for one developer and an AI coding agent.

**Stop re-explaining your project every session. Stop the silent architectural drift.**
One small, local-first Python **MCP** server — works with Claude Code, Codex, Cursor, VS Code, Gemini CLI and any other MCP client.

![CI](https://github.com/magnetoid/torsor-helper/actions/workflows/ci.yml/badge.svg)
![release](https://img.shields.io/badge/release-v0.8.0-success)
![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![protocol](https://img.shields.io/badge/protocol-MCP-7c3aed)
![local-first](https://img.shields.io/badge/local--first-no%20API%20key-00a3a3)

</div>

---

> **Your AI agent has amnesia.** Every new session starts from zero. Mid-session it forgets the rules you set an hour ago. It rebuilds the helper you already wrote, re-introduces the pattern you explicitly rejected, quietly drifts from your architecture — and sometimes imports a package that doesn't even exist. **torsor-helper** is a small helper for solo vibe coding that owns the four things the agents don't do natively: **committed, in-repo project memory** that follows `git clone` and works across Claude Code / Codex / Cursor (their built-in memories are machine-local); a **guard** that enforces your ADR rules as a hook, not just a prompt; a small **code map** with `impact` blast radius; and an offline **hallucinated-dependency check**. Plus a **Coach** for health nudges and a **command book** so the agent stops re-deriving how to run your tests. All local-first, no API key.

**Contents:** [Install](#-install) · [Quick start](#-quick-start) · [Connect your agent](#-connect-your-agent) · [Why](#-why) · [Every feature](#-every-feature--what-it-solves--when-to-use-it) · [How it works](#️-how-it-works) · [Usage](#️-usage) · [Status](#-status--roadmap) · [Contributing](#-contributing--releasing)

> **New here / vibe-coding a startup?** Jump to [**Every feature — what it solves & when to use it**](#-every-feature--what-it-solves--when-to-use-it) for a plain-language guide to which tool helps with what.
>
> 📚 **Step-by-step guides:** [**Vibe-coding guide**](docs/vibe-coding-guide.md) — how to use torsor while building fast with an AI agent (start here) · [**How to install**](docs/how-to-install.md) — every install path + client setup · [**How to use**](docs/how-to-use.md) — the day-to-day workflow, ADR rules, CI, and the full CLI/MCP reference.

## 📦 Install

`torsor-helper` is a small, local-first Python package (Python ≥ 3.11). *(Full walkthrough incl. troubleshooting: [docs/how-to-install.md](docs/how-to-install.md).)*

**Available now — install the global `torsor` command straight from GitHub (no PyPI needed):**
```bash
uv tool install "git+https://github.com/magnetoid/torsor-helper"
# or:  pipx install "git+https://github.com/magnetoid/torsor-helper"
# with semantic embeddings:  uv tool install "torsor-helper[embeddings] @ git+https://github.com/magnetoid/torsor-helper"
# with JS/TS/Go in the map:  uv tool install "torsor-helper[languages] @ git+https://github.com/magnetoid/torsor-helper"
```

**From PyPI**, once a release is published (the workflow runs the full suite, the guard and a wheel smoke-test before it publishes — see [PUBLISHING.md](PUBLISHING.md); tags so far: v0.4.0, v0.6.0):
```bash
uv tool install torsor-helper     # or: pipx install torsor-helper / pip install torsor-helper
uv tool install "torsor-helper[languages]"   # + JS/TS/Go in the map (official tree-sitter grammar wheels)
uvx torsor-helper --help          # ephemeral, no install
```

**From a local clone (for development):**
```bash
git clone https://github.com/magnetoid/torsor-helper && cd torsor-helper
uv run torsor --help              # uv resolves the env from pyproject automatically
```

**Upgrade:** `uv tool upgrade torsor-helper` (or `pipx upgrade torsor-helper`).

> Without the `[embeddings]` extra, recall uses a deterministic offline hashing fallback — everything works with no model download and no API key.

## 🚀 Quick start

```bash
cd your-project
torsor init --write          # scaffold .torsor/ AND write a project .mcp.json
torsor doctor                # sanity-check
```

`torsor init` creates the `.torsor/` pyramid (commit it — it's your project's memory). `--write` drops a `.mcp.json` so MCP clients that read it (**Claude Code** especially) auto-detect torsor-helper. That's it — your agent now has memory.

Then put your standing rules where the agent reads them for free:

```bash
torsor rules --write AGENTS.md     # or CLAUDE.md — refresh any time you record a new ADR
```

`torsor rules` distills your charter's non-negotiable principles plus every machine-readable ADR rule into a compact (~600-token, budget-capped) digest, written into a managed block in your agent's prompt file. The agent sees the constraints **at prompt time — no tool calls, no rediscovery, no burned context** — and `torsor guard` still enforces the same rules deterministically in CI. Re-running replaces the block, never duplicates it.

## 🔌 Connect your agent

torsor-helper is a standard **MCP stdio server** — the command is `torsor mcp`. Point any MCP client at it. `torsor init --client <name>` prints exact, copy-paste config for your tool and says where it goes.

### Claude Code — *one command*
Paste this into the Claude Code terminal — it installs `torsor` and wires up the current project, then reload MCP servers:
```bash
curl -fsSL https://raw.githubusercontent.com/magnetoid/torsor-helper/main/scripts/install.sh | bash
```
Prefer not to pipe a script? The equivalent two commands:
```bash
uv tool install "git+https://github.com/magnetoid/torsor-helper"   # installs the `torsor` command
torsor init --write                                                  # scaffold .torsor/ + write ./.mcp.json
```
Claude Code auto-detects torsor-helper from `.mcp.json`. To register it for **all** projects instead: `claude mcp add --scope user torsor-helper -- torsor mcp` (or `install.sh --global`).

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

### VS Code / GitHub Copilot
VS Code uses its own `servers` shape in **`.vscode/mcp.json`** (or Command Palette → *MCP: Add Server*). `torsor init --client vscode` prints it:
```json
{ "servers": { "torsor-helper": { "type": "stdio", "command": "torsor", "args": ["mcp"] } } }
```

### Supported clients

| Client | `--client` | Config goes in |
|---|---|---|
| Claude Code | `claude-code` | project `.mcp.json` (via `torsor init --write`) or `claude mcp add` |
| Cursor | `cursor` | `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global) |
| Codex CLI | `codex` | `~/.codex/config.toml` |
| VS Code / Copilot | `vscode` | `.vscode/mcp.json` (`servers` shape — the snippet handles it) |
| Gemini CLI | `gemini` | `~/.gemini/settings.json` (global) or `.gemini/settings.json` (project) |
| Any other MCP client | `other` | prints the standard `mcpServers` JSON block — most clients accept it as-is |

> **Note:** the config uses `command: "torsor"`, which requires the `torsor` command on your PATH (`uv tool install` / `pipx install`). Running ephemerally instead? Use `"command": "uvx", "args": ["torsor-helper", "mcp"]`.

## ⏱️ The 30-second version

| When | You (or your agent) do | What it buys you |
|---|---|---|
| **Once per project** | `torsor init --write`, fill `charter.md` + your architecture rules, commit `.torsor/` | Every future session starts from the same truth — no more re-explaining the project |
| **Once per project** | `torsor rules --write AGENTS.md` (or `CLAUDE.md`), or `torsor rules --scoped` for Claude Code | Your rules ride along in the agent's prompt file — **zero tool-call tokens** to follow them; `--scoped` loads each rule only when a governed file is touched |
| **Every session** | `torsor hooks install` once — then the digest is injected at session start (and after `/compact`) and `handoff()` is written at session end, automatically | No blank-slate starts; the next session resumes where this one stopped |
| **While coding** | agent calls `recall()` / `bootstrap_session(topic)` / `impact()` before changing things | Finds prior decisions and existing code instead of re-inventing or breaking it |
| **Every edit** (with hooks installed) | nothing — the `PreToolUse` edit gate checks the *proposed* Edit/Write against your ADRs | Drift is flagged with the ADR cited **before** it lands; advisory by default, `guard_on_edit = "block"` to enforce |
| **Before commit / in CI** | `torsor guard --strict` · `torsor deps` | Catches architectural drift and hallucinated packages the moment they appear |
| **Weekly-ish** | `torsor coach` · `torsor clean` | Health and hotspot nudges; dead artefacts reclaimed |


## 💡 Why

AI coding agents are brilliant in the moment and forgetful over time. Claude Code, Codex and Cursor each have a memory of sorts — but it lives on one machine, in one tool, and does not follow the repo. torsor-helper puts the memory **in the repo**, where `git clone` carries it and every agent reads the same thing:

| Failure mode | What it feels like | torsor-helper's answer |
|---|---|---|
| 🧠 **Context Collapse** | New chat = blank slate; long chats drift; the agent loses how files connect. | Committed pyramid of charter → ADRs → progress + `bootstrap_session` + `handoff`; **contextual breadcrumbs** so situating terms are findable |
| 🔭 **Context Myopia** | Optimizes for what's *recent*, not *important*. | Stability-ordered tiers + hybrid recall; **importance decay** + **MMR diversity** so durable, distinct memory floats up |
| 🏛️ **Lost Architectural Intent** | Layering/naming rules stop being followed; rejected patterns return. | ADRs-as-rules + `verify`, enforced as a **hook on every edit**, not just a line in a prompt; **layering/seam rules**, a **CI baseline**, and **ADR supersedes** |
| ♻️ **Blind edits** | One regenerated symbol silently breaks far-off callers ([~8× more duplication](https://www.builder.io/m/explainers/vibe-coding-limitations) too). | Symbol map with **real reference edges** + `impact` blast-radius; `bootstrap_session(topic)` shows what already exists before building |
| 📦 **Phantom deps** | Imports packages that don't exist ([slopsquatting](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen)). | Offline `deps` check |

<sub>**Why "torsor"?** A *torsor* is a space that looks like a group but has **no fixed origin** — you can only measure *differences* between points. That's exactly drift detection: your architecture is the reference frame, drift is the measured delta.</sub>

## 🧰 Every feature — what it solves & when to use it

New to torsor (or to vibe-coding in general)? This is the plain-language map: **what each feature is, the pain it kills, and when you'd reach for it.** Nearly everything is an MCP tool your agent calls *and* a CLI command you can run yourself.

### 🧠 Memory & continuity — *"my agent forgets everything"*
| Feature | What it does | Reach for it when… |
|---|---|---|
| **Charter / pyramid** (`.torsor/`) | Plain-Markdown files holding your project's purpose, architecture, decisions, and current state. Committed, so it follows the repo. | **Set up once.** Fill `charter.md` + `architecture/` so every session starts from the same truth. |
| `bootstrap_session()` | A budgeted summary of the whole project, loaded at the start of a chat. | **Every new session** — the first thing the agent should call so it's not a blank slate. |
| `torsor primer --write` | **Token saver:** writes a budgeted project primer + token-efficiency habits into AGENTS.md/CLAUDE.md, so orientation costs zero tool calls. | **Once, then after big changes** — the cheapest tokens are the ones never spent. |
| `recall(query)` | Hybrid semantic + keyword search over all your memory, your own docs, and notes. | The agent asks *"have we decided X?"* / *"how does auth work here?"* before writing code. |
| `remember(content)` · `update_active(...)` | The agent writes down what it learns / the current focus. | After a decision, a gotcha, or finishing a chunk — so the next session inherits it. |
| `handoff()` | A structured end-of-session summary that seeds the next session. | **End of a work session**, before you close the chat. |
| `torsor clean` | Reclaims what torsor stopped needing: orphaned map notes, dead index rows, and — only with `--expire-journals` — journals past `clean.journal_retention_days`. **Dry run by default.** | **Whenever `.torsor/` feels cluttered** — especially after renaming or deleting source files. |

### 🗺️ Understanding the codebase — *"the agent doesn't see how files connect"*
| Feature | What it does | Reach for it when… |
|---|---|---|
| `torsor map` | Builds a symbol map (functions/classes) **+ real reference edges** ("who calls what") — Python via stdlib `ast`; JavaScript/TypeScript/TSX and Go via the optional `[languages]` extra. | **After big changes** (it auto-skips when nothing changed). Powers everything below. |
| `bootstrap_session(topic)` | Surfaces the architecture + relevant existing symbols for a topic. | Before building a feature — *"what already exists around payments?"* |
| `torsor impact <symbol>` | Every caller of a symbol **and** every decision or learning that mentions it — the **blast radius**, in code and in intent. | **Before you let the agent change/rename a function** — see what breaks, and why it was written that way. |
| `torsor connect <from> <to>` | Shortest call-graph path between two symbols. | *"How does the request handler reach the database?"* before a refactor. |

### 🛡️ Keeping your architecture — *"it quietly drifts from the plan"*
| Feature | What it does | Reach for it when… |
|---|---|---|
| `record_decision(...)` (ADRs) | Records an Architecture Decision — optionally with machine-readable **rules**. | You make a load-bearing call (*"the domain layer may not import the web layer"*). |
| `torsor guard` | Flags code that violates your ADR rules (`forbid_import`, layering, required seams…). | **Before every commit / in CI** (`--strict`). Catches drift the moment it appears. |
| `torsor hooks install` | Wires the same check into Claude Code's `PreToolUse` so every proposed edit is checked against your ADRs **before it lands** — plus session-start digest and auto-handoff. | **Once per project.** This is the difference between a rule in a prompt and a rule that holds. |
| `guard --update-baseline` | Grandfathers existing violations so `--strict` fails only on **new** drift. | **Adopting torsor on an existing/messy repo** — turn on CI without a wall of red. |
| `record_decision(..., supersedes=…)` | Marks an old ADR superseded so stale intent stops resurfacing in recall. | You change your mind — the new decision replaces the old cleanly. |
| `torsor verify` | One pass/fail gate: guard + deps + staleness, optionally your recorded `test` command. | As a completion check in CI or an agent loop. |

### 📦 Supply-chain safety — *"the AI imported a package that doesn't exist"*
| Feature | What it does | Reach for it when… |
|---|---|---|
| `torsor deps` | Flags imports that match **no** stdlib / installed / declared / first-party package — a possible **hallucinated dependency** ("slopsquatting"). Python, JS/TS, Go. | **Before `pip install`-ing what the agent suggested.** ~5–20% of AI imports don't exist; some are malware bait. Fully offline. |

### 🧭 The Coach — *"tell me what to fix, don't make me hunt"*
Run `torsor coach` (or it's pushed at session start). It's advisory, ranked, and **decays so it never nags** — and it tells you what you fixed since last time:
| Coach signal | What it tells you | Why it matters |
|---|---|---|
| `thin` / `stale` / `uncharted` | Your charter is still a template / active context is stale / modules aren't mapped. | Keeps the memory layer actually filled in and current. |
| `hotspot` | The files with the most churn × complexity — **fix/test these first**. | Tells you *where* the risk concentrates, not just that risk exists. |
| `phantom_dep` | An import resolves to no known package (see `torsor deps`). | Early warning on hallucinated dependencies. |
| `dangling_link` | A `[[wikilink]]` or file path in memory that no longer exists (see `torsor stale`). | Memory that contradicts the code is worse than no memory. |

### 💸 Spending fewer tokens — *"my agent keeps re-deriving the same things"*
| Feature | What it does | Reach for it when… |
|---|---|---|
| `torsor commands` | A **learned command book** — record `test`/`build`/`lint`/`run` once; persisted in committed Markdown and shown in the primer. | The agent rediscovers *"how do I run the tests here?"* every session. Record it once, replay forever. |
| `torsor primer` / `torsor rules` | Budgeted managed blocks in your prompt file: orientation and standing rules at **zero tool-call cost**. | Once, then after big changes or new ADRs. |

```bash
torsor commands --add test 'uv run pytest' --note 'run the suite'
torsor commands --add lint 'uv run ruff check src tests'
torsor commands              # list them
torsor commands --run test   # replay one from the repo root
```
Your agent calls `list_commands()` (or just reads the primer) and runs the exact command — no trial and error. The MCP server **records and lists** commands but never executes them; the agent runs them with its own shell.

> **Rule of thumb:** start a session → `bootstrap_session`; before building → `recall` / `bootstrap_session(topic)`; before changing a symbol → `impact`; before installing a suggested package → `deps`; before committing → `verify`; end of session → `handoff`; weekly → skim `coach`.

## ✨ What's new

See **[CHANGELOG.md](CHANGELOG.md)** — the one that is kept current.

## ⚙️ How it works

Your project's memory lives as **plain Markdown you own** — git-versioned, Obsidian-readable, editable by you *and* the agent. A **disposable index** (SQLite FTS5 + local-embedding vectors + a wiki-link graph) is *derived* from those files for instant semantic recall. A single Python **MCP server** serves it all to any agent.

> **One rule:** Markdown is always the source of truth. The index is throwaway — delete it, rebuild it, never fear it.

### 🔺 The pyramid

Five Markdown tiers under `.torsor/`, ordered by **stability** — the broad, stable base loads first; the volatile tip changes every session. Your project's own `README.md` and `docs/` are indexed in place as a sixth, read-only tier.

```
                 ╱╲
                ╱T4╲            EPISODIC      memory/       observations · learnings · handoffs
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

### 🔬 Under the hood — how each part works

Everything below is **derived from your Markdown** and rebuildable. Delete `.torsor/.index/` any time; the next command rebuilds it.

- **Recall (`recall`)** — every note is indexed three ways: **FTS5** keyword search, **vector** embeddings (a local `fastembed` model, or a deterministic offline hash fallback), and a **wiki-link graph**. A query fuses them with **Reciprocal Rank Fusion**, then re-weights by tier (stable tiers rank higher), recency, an **importance multiplier** (notes you recall often float up; charter/architecture never decay), and a 1-hop link-graph boost. **MMR** drops near-duplicate hits so scarce context isn't wasted, and results are packed to a token budget. Indexing is incremental (content-hash diff) and self-heals when the embedder changes.
- **The map (`map` / `impact` / `connect`)** — a cartographer over a per-language registry (Python via stdlib `ast`, always on; JavaScript/TypeScript/TSX and Go via the official tree-sitter grammar wheels behind the optional `[languages]` extra) extracts every function/class/method and, crucially, **real reference edges** ("who calls what") by resolving names — not substring matching, so comments and strings never inflate counts. `impact` walks those edges to show a symbol's blast radius; `connect` finds the shortest path between two symbols — language-agnostic since it's built on the same edge shape. A repo fingerprint lets `map` skip entirely when nothing changed; without `[languages]` installed, everything above quietly stays Python-only (ADR 0013).
- **The guard (`guard` / `verify` / hooks)** — ADRs carry machine-readable `rules:` in their frontmatter (`forbid_import`, `forbid_layer_import`, `require_import`, `forbid_pattern`, `forbid_cycle`). The guard checks changed files against them deterministically (AST + regex), citing the ADR. It's **advisory by default**; `--strict` fails CI, a committed **baseline** grandfathers existing debt so only *new* drift fails, and `torsor hooks install` runs the same check on every proposed edit inside Claude Code.
- **The Coach (`coach` / `recommend`)** — surfaces ranked, evidence-backed nudges: thin/stale/uncharted memory, `hotspot` (churn × complexity), `phantom_dep` (a hallucinated import), `dangling_link` (memory pointing at code that is gone). Each **decays** so it never nags; a 3-item digest rides along in `bootstrap_session`.
- **The command book (`commands`)** — the learned commands and the rules/primer blocks live in your prompt file (zero tool-call cost). torsor never calls an LLM — it makes the exact answers cheap to fetch.

> **The one rule:** Markdown is always the source of truth. The SQLite index, the symbol map — all derived, all disposable, never something to fear losing.

## 🛠️ Usage

*(Full day-to-day guide — first hour, daily loop, rule kinds, CI recipes, FAQ: [docs/how-to-use.md](docs/how-to-use.md).)*

### CLI

| Command | What it does |
|---|---|
| `torsor init [--write] [--client <name>]` | Scaffold `.torsor/`; `--write` emits `.mcp.json`; `--client` prints that client's config |
| `torsor --version` | Print the installed torsor-helper version |
| `torsor mcp` | Run the MCP server over stdio |
| `torsor doctor` | Verify the project is healthy |
| `torsor index [--full]` | Build/refresh the derived search index |
| `torsor map [--force]` | Generate the repository symbol map + reference edges (skips when unchanged; `--force` to re-scan) |
| `torsor impact <symbol>` | Blast radius of a symbol — who references it across files, and what was decided about it |
| `torsor connect <from> <to> [--max-hops N]` | Shortest call-graph path between two symbols |
| `torsor primer [--write <file>] [--client <name>] [--tokens N]` | **Token saver:** budgeted prompt-time project primer (charter + architecture + map + token-efficiency habits) — zero discovery tool-calls per session |
| `torsor rules [--write <file>] [--client <name>] [--scoped]` | Print a compact agent-rules digest (charter principles + ADR rules); `--write`/`--client` maintains a managed block in `AGENTS.md`/`CLAUDE.md`; `--scoped` writes one path-scoped Claude Code rule file per ADR under `.claude/rules/torsor/` |
| `torsor deps [files…] [--strict]` | Flag imports resolving to no known package — possible hallucinated dependencies (offline; Python, JS/TS, Go) |
| `torsor guard [files…] [--strict] [--severity <lvl>] [--json] [--update-baseline]` | Flag ADR-rule violations; `--strict` fails CI on **new** drift; `--json` for machine-readable findings |
| `torsor verify [files…] [--strict] [--run-tests] [--json]` | One pass/fail gate: guard + deps + staleness, optionally your recorded `test` command |
| `torsor stale [--mark\|--unmark]` | Memory that contradicts the code: dangling `[[wikilinks]]` and dead file paths |
| `torsor coach [--dismiss <key>] [--limit N]` | Health + **hotspot** + **phantom-dep** + **dangling-link** recommendations, plus what you fixed since last time |
| `torsor clean [--apply] [--deep] [--expire-journals]` | Garbage-collect derived artefacts: orphaned map notes, dead index rows (+VACUUM); `--deep` drops the whole index; `--expire-journals` also deletes journals past the retention window. Dry run unless `--apply` |
| `torsor commands [--add NAME COMMAND] [--run name]` | Record & replay project commands (test/build/lint) so agents don't re-derive them |
| `torsor stats [--json]` | Notes per tier, map size, index size, what gets recalled most |
| `torsor hooks install\|uninstall\|status` | Wire auto-capture (session-start digest, edit gate, auto-handoff) into git and Claude Code |
| `torsor recall` · `remember` · `active` · `handoff` · `bootstrap` · `intent` · `decision` | The memory operations from the shell — same as the MCP tools, for scripting and debugging |

### MCP tools (what the agent calls)

| Tool | What it does |
|---|---|
| `bootstrap_session(topic?)` | Budgeted summary of the whole pyramid at session start (+ a Coach digest); with a topic, the architecture and existing symbols around it |
| `recall(query)` | Hybrid search over memory + wiki + your docs (vector + FTS5, fused via RRF) |
| `remember(content)` · `update_active(...)` | Self-editing memory the agent maintains as it works |
| `handoff()` | Structured end-of-session summary → seeds the next session |
| `map_repo(force?)` · `impact(symbol, to?)` | Build the symbol map; a symbol's caller blast radius, or with `to` the call path between two symbols |
| `record_decision(..., supersedes?)` | Record ADRs (that become rules) |
| `get_rules()` | The standing constraints — load once per session if not already in the prompt file |
| `check_dependencies(files?)` | Flag hallucinated imports (slopsquatting; Python, JS/TS, Go) |
| `verify(files?, severity?)` | One JSON verdict over guard + deps + staleness — before a commit, or as a loop's completion check |
| `record_command(...)` · `list_commands()` | The learned command book |
| `recommend()` · `dismiss_recommendation(key)` | The Coach (health · hotspots · phantom-deps · dangling links) |

### A typical loop
1. **Once:** `torsor init --write`, fill in `charter.md` + `architecture/`, commit `.torsor/`; `torsor rules --write AGENTS.md` so the rules live in the prompt; `torsor hooks install` so the loop below runs itself.
2. **Each session:** the agent calls `bootstrap_session()` → gets your charter, architecture, active state, recent memory, and a Coach nudge or two.
3. **While working:** it `recall()`s prior decisions, `bootstrap_session(topic=...)` before changes, `impact()` before touching a shared symbol, and `remember()`s what it learns.
4. **Before a commit:** `verify()` flags anything that violates your ADR rules, imports that don't exist, and memory that drifted from the code.
5. **End of session:** `handoff()` writes a summary the next session resumes from.
6. **Periodically:** `torsor coach` for health nudges; `torsor clean` to see what's become dead weight (then `--apply`).

### 🩺 The Coach
An **independent advisor that sits beside your coding, never in it.** It watches project health and nudges — *"your `architecture/` is still the template", "12 decisions but 0 rules", "`billing/charge.py` is your top hotspot"* — each with **evidence + a concrete action**, ranked by severity, and **decaying** so it never nags. Pull it (`torsor coach` / `recommend()`), or get it **pushed** as a short digest at session start (silent when healthy).

## 🧩 What's inside

A small, layered toolkit — pure core under thin adapters (the agent/CLI never reach past `operations`):

```
src/torsor_helper/
├─ models.py        # Pydantic models: Note, Symbol, SymbolEdge, Rule, Violation, Recommendation, …
├─ paths.py         # .torsor/ layout            store.py     # Markdown I/O (frontmatter + wikilinks)
├─ templates.py     # seed pyramid               budget.py    # token budgeting
├─ config.py        # torsor.toml                db.py        # SQLite: FTS5 + vectors + wiki edges + symbols + symbol_edges
├─ embeddings.py    # FastEmbed | Hashing        indexer.py   # incremental reindex + contextual breadcrumbs
├─ recall.py        # keyword fallback           search.py    # hybrid RRF + importance decay + MMR
├─ snippets.py      # section-aware snippets      cartographer.py  # symbols + reference edges (dispatches to languages/)
├─ languages/       # python.py (ast) · treesitter.py + javascript.py/go.py (optional `[languages]` extra)
├─ guard.py         # ADR rules → drift detection baseline.py  # committed drift baseline (ratchet)
├─ deps.py          # offline slopsquatting guard hooks.py     # git + Claude Code hook installers
├─ coach/           # health · hotspots · staleness · report · state
├─ operations/      # orchestration incl. impact() (the tested core)
├─ server.py        # MCPServer adapter           cli.py       # Typer CLI
```

Everything is **dogfooded**: this repo has its own `.torsor/` with real ADRs whose layering rules `torsor guard` enforces, a `torsor map` of its own symbols **and reference edges**, and a clean `torsor coach` / `torsor deps` run. Lint-clean and type-checked, every feature offline-testable.

## 📍 Status & roadmap

What shipped when is in **[CHANGELOG.md](CHANGELOG.md)**; this section is what is true now and what is next.

Everything is dogfooded: this repo has its own `.torsor/`, its ADRs carry the
machine-readable rules that `torsor guard` enforces against this codebase in
CI, and `torsor map` covers its own symbols and reference edges.

**Recently hardened:**

- **Safety** · installing hooks can no longer damage a `.claude/settings.json` it cannot parse, or remove a hook it did not write; every caller-supplied path is contained to the project root; command execution is CLI-only.
- **Performance** · recall went from 7.6s to ~0.5s and a cold map from 164s to 25s on a generated 5 000-note corpus (`tests/bench/`).
- **Correctness** · guard scopes are path-aware (`*` no longer crosses `/`, `**` spans directories), wikilink aliases resolve, a partial map can no longer shrink a committed file, and the hashing fallback no longer invents search results for queries with no lexical basis.
- **Scope** · trimmed to what one developer with an agent actually uses: memory, guard, map + impact, deps, Coach, command book. Everything else was removed rather than left half-maintained.

**Next:**

- **Sampling-based semantic drift** · the guard is deterministic by design; a sampling check is the long-standing open idea.
- **Better topic loading** · a tighter link between the memory index and the symbol graph so "what exists around X" gets sharper.

## 🧪 Built with

MCP Python SDK 2.x · Typer · Pydantic · PyYAML · SQLite (FTS5) · NumPy · stdlib `ast` — *local-first, no API key required.* Optional `fastembed` extra for semantic embeddings. The repo map covers Python via stdlib `ast`; JavaScript/TypeScript/TSX and Go via the `[languages]` extra (official tree-sitter grammar wheels, offline — never `tree-sitter-language-pack`, which downloads its grammars at runtime). The drift guard is deterministic (ADR rules → AST/regex, plus JS/TS/Go import-specifier checks when `[languages]` is installed).

## 📚 Design & prior art

Architectural decisions live as ADRs in [`.torsor/architecture/decisions/`](.torsor/architecture/decisions/) — the same ones the guard enforces. torsor-helper stands on the shoulders of [Cline Memory Bank](https://docs.cline.bot/prompting/cline-memory-bank), [mem0/OpenMemory](https://mem0.ai/openmemory), [Letta/MemGPT](https://docs.letta.com/), [Zep/Graphiti](https://github.com/getzep/graphiti), [basic-memory](https://github.com/basicmachines-co/basic-memory), [cognee](https://github.com/topoteretes/cognee), [Aider's repo map](https://aider.chat/docs/repomap.html), [Serena](https://github.com/oraios/serena), [CodeScene](https://codescene.com/), [ArchUnit](https://www.archunit.org/) / [dependency-cruiser](https://github.com/sverweij/dependency-cruiser), [Anthropic Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval), and [GitHub spec-kit](https://github.com/github/spec-kit).

## 🩺 Troubleshooting

Run **`torsor doctor`** first. It checks the things that fail quietly — a stale
map, semantic recall silently on the hashing fallback, hooks that were never
installed, an ADR rule that does not parse — and tells you the command that
fixes each one. `--json` if you want to act on it in a script.

| Symptom | What it usually is |
|---|---|
| `torsor: command not found` | The install put it somewhere off PATH. `uv tool update-shell`, or run `python -m torsor_helper`. |
| The agent does not see torsor | The MCP client did not pick up the config. `torsor init --client <name>` prints the exact file and contents for your tool. |
| Recall returns nothing useful | `doctor` will say if you are on the hashing fallback. Install the `embeddings` extra for semantic recall; without it, recall is lexical only and will not invent matches. |
| `impact` or `connect` finds nothing | The map is stale or was never built. `torsor map`. |
| The guard passes but I expected a violation | With no file arguments it checks *git-changed* files, so on a clean tree it checks nothing. Pass paths, or `torsor guard $(git ls-files '*.py')`. |
| The index looks wrong | It is derived and disposable: `torsor clean --apply --deep --yes`, then `torsor index`. Your Markdown is untouched. |

More: [how to install](docs/how-to-install.md) · [how to use](docs/how-to-use.md) · [security](SECURITY.md)

## 🤝 Contributing & releasing

`uv run --extra dev --extra languages pytest` · `uv run --with ruff ruff check src tests`. Releasing: see [PUBLISHING.md](PUBLISHING.md).

## License

[MIT](LICENSE) © Marko Tiosavljevic.

---

<div align="center"><sub>Author: <a href="https://mtiosavljevic.com">Marko Tiosavljevic</a> · <a href="https://imbamarketing.com">Imba Marketing</a></sub><br>
<sub>Built with the <a href="https://claude.com/claude-code">Claude Code</a> superpowers workflow — brainstorm → spec → plan → TDD → review.</sub></div>
