<div align="center">

# 🧭 torsor-helper

### Memory · guardrails · coaching — for AI coding agents.

**Stop re-explaining your project every session. Stop the silent architectural drift.**
One small Python **MCP** server — works with *every* AI coding tool (Claude Code, Codex, Cursor, …).

![CI](https://github.com/magnetoid/torsor-helper/actions/workflows/ci.yml/badge.svg)
![status](https://img.shields.io/badge/release-v0.4%20token%20thrift-success)
![tests](https://img.shields.io/badge/tests-328%20passing-brightgreen)
![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![protocol](https://img.shields.io/badge/protocol-MCP-7c3aed)
![local-first](https://img.shields.io/badge/local--first-no%20API%20key-00a3a3)

</div>

---

> **Your AI agent has amnesia.** Every new session starts from zero. Mid-session it forgets the rules you set an hour ago. It rebuilds the helper you already wrote, re-introduces the pattern you explicitly rejected, quietly drifts from your architecture — and sometimes imports a package that doesn't even exist. **torsor-helper** is the persistent **brain** that fixes the forgetting, a **guardrail** that catches the drift, and a **coach** that keeps nudging your project back toward health — all local-first, no API key.

**Contents:** [Why](#-why) · [Every feature — what & when](#-every-feature--what-it-solves--when-to-use-it) · [Token thrift](#-token-thrift--spend-fewer-cheaper-tokens) · [What's new](#-whats-new) · [How it works](#-how-it-works) · [Install](#-install) · [Connect your agent](#-connect-your-agent-claude-code-codex-cursor-) · [Usage](#-usage) · [Team / HTTP mode](#-team--http-mode) · [What's inside](#-whats-inside) · [Status](#-status--roadmap) · [Design](#-design--prior-art)

> **New here / vibe-coding a startup?** Jump to [**Every feature — what it solves & when to use it**](#-every-feature--what-it-solves--when-to-use-it) for a plain-language guide to which tool helps with what.
>
> 📚 **Step-by-step guides:** [**Vibe-coding guide**](docs/vibe-coding-guide.md) — how to use torsor while building fast with an AI agent (start here) · [**How to install**](docs/how-to-install.md) — every install path + setup for all 20 supported clients · [**How to use**](docs/how-to-use.md) — the day-to-day workflow, ADR rules, CI, and the full CLI/MCP reference.

## ⏱️ The 30-second version

| When | You (or your agent) do | What it buys you |
|---|---|---|
| **Once per project** | `torsor init --write`, fill `charter.md` + your architecture rules, commit `.torsor/` | Every future session starts from the same truth — no more re-explaining the project |
| **Once per project** | `torsor rules --write AGENTS.md` (or `CLAUDE.md`), or `torsor rules --scoped` for Claude Code | Your rules ride along in the agent's prompt file — **zero tool-call tokens** to follow them; `--scoped` loads each rule only when a governed file is touched |
| **Every session** | `torsor hooks install` once — then the digest is injected at session start (and after `/compact`) and `handoff()` is written at session end, automatically | No blank-slate starts; the next session resumes where this one stopped |
| **While coding** | agent calls `recall()` / `get_intent()` / `impact()` before changing things | Finds prior decisions and existing code instead of re-inventing or breaking it |
| **Before commit / in CI** | `torsor guard --strict` · `torsor deps` | Catches architectural drift and hallucinated packages the moment they appear |
| **Weekly-ish** | `torsor coach` · `torsor consolidate` · `torsor clean` | Hotspot/coupling nudges; journal noise distilled into clean insights; dead artefacts reclaimed |


## 💡 Why

AI coding agents are brilliant in the moment and forgetful over time:

| Failure mode | What it feels like | torsor-helper's answer |
|---|---|---|
| 🧠 **Context Collapse** | New chat = blank slate; long chats drift; the agent loses how files connect. | Pyramidal wiki + `bootstrap_session` + `handoff`; **contextual breadcrumbs** so situating terms are findable |
| 🔭 **Context Myopia** | Optimizes for what's *recent*, not *important*. | Stability-ordered tiers + hybrid recall; **importance decay** + **MMR diversity** so durable, distinct memory floats up |
| 🏛️ **Lost Architectural Intent** | Layering/naming rules stop being followed; rejected patterns return. | ADRs-as-rules + `check_drift`; **layering/seam rules**, a **CI baseline**, and **ADR supersedes** |
| ♻️ **Duplication & drift** | Rebuilds code that already exists ([~8× more duplication](https://www.builder.io/m/explainers/vibe-coding-limitations)). | Symbol map with **real reference edges** + the Coach's `reuse` & **hotspot** recs |
| 📦 **Phantom deps & blind edits** | Imports packages that don't exist ([slopsquatting](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen)); one regenerated symbol silently breaks far-off callers. | Offline `deps` check + `impact` blast-radius (who-calls-what edges) |

Most tools fix *one* of these. **torsor-helper combines four ideas no one else puts together** — a pyramidal wiki, an external semantic memory, a symbol-level repo map, and a drift guard — plus a **Coach** that proactively recommends fixes over time. See [What's new](#-whats-new).

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

### 🔬 Under the hood — how each part works

Everything below is **derived from your Markdown** and rebuildable. Delete `.torsor/.index/` any time; the next command rebuilds it.

- **Recall (`recall`)** — every note is indexed three ways: **FTS5** keyword search, **vector** embeddings (a local `fastembed` model, or a deterministic offline hash fallback), and a **wiki-link graph**. A query fuses them with **Reciprocal Rank Fusion**, then re-weights by tier (stable tiers rank higher), recency, an **importance multiplier** (notes you recall often float up; charter/architecture never decay), and a 1-hop link-graph boost. **MMR** drops near-duplicate hits so scarce context isn't wasted, and results are packed to a token budget. Indexing is incremental (content-hash diff) and self-heals when the embedder changes.
- **The map (`map` / `get_intent` / `impact`)** — a stdlib-`ast` cartographer extracts every function/class/method and, crucially, **real reference edges** ("who calls what") by resolving names — not substring matching, so comments and strings never inflate counts. `impact` walks those edges to show a symbol's blast radius; `find` fuzzy-searches files + symbols, ranked by match quality and frecency. A repo fingerprint lets `map` skip entirely when nothing changed.
- **The guard (`guard` / `check_drift`)** — ADRs carry machine-readable `rules:` in their frontmatter (`forbid_import`, `forbid_layer_import`, `require_import`, `forbid_pattern`). The guard checks changed files against them deterministically (AST + regex), citing the ADR. It's **advisory by default**; `--strict` fails CI, and a committed **baseline** grandfathers existing debt so only *new* drift fails.
- **The Coach (`coach` / `recommend`)** — surfaces ranked, evidence-backed nudges: stale/thin files, `reuse` (a symbol already exists), `hotspot` (churn × complexity), `coupling` (files that always change together but aren't linked), `regression` (complexity rose since the last snapshot), `phantom_dep` (a hallucinated import). Each **decays** so it never nags; a 3-item digest rides along in `bootstrap_session`.
- **Token thrift (`commands` / `recipes` / `models`)** — the learned command book and the rules/primer blocks live in your prompt file (zero tool-call cost); `recipes` learns which deterministic lookups recur; `models` publishes a cheap-vs-smart routing policy your harness follows. torsor never calls an LLM — it makes the exact answers cheap to fetch. See [Token thrift](#-token-thrift--spend-fewer-cheaper-tokens).

> **The one rule:** Markdown is always the source of truth. The SQLite index, the symbol map, the frecency counters — all derived, all disposable, never something to fear losing.

## 🧰 Every feature — what it solves & when to use it

New to torsor (or to vibe-coding in general)? This is the plain-language map: **what each feature is, the pain it kills, and when you'd reach for it.** Everything is an MCP tool your agent calls *and* a CLI command you can run yourself.

### 🧠 Memory & continuity — *"my agent forgets everything"*
| Feature | What it does | Reach for it when… |
|---|---|---|
| **Charter / pyramid** (`.torsor/`) | Plain-Markdown files holding your project's purpose, architecture, decisions, and current state. | **Set up once.** Fill `charter.md` + `architecture/` so every session starts from the same truth. |
| `bootstrap_session()` | A budgeted summary of the whole project, loaded at the start of a chat. | **Every new session** — the first thing the agent should call so it's not a blank slate. |
| `torsor primer --write` | **Token saver:** writes a budgeted project primer + token-efficiency habits into AGENTS.md/CLAUDE.md, so orientation costs zero tool calls. | **Once, then after big changes** — the cheapest tokens are the ones never spent. |
| `recall(query)` | Hybrid semantic + keyword search over all your memory and notes. | The agent asks *"have we decided X?"* / *"how does auth work here?"* before writing code. |
| `remember(content)` · `update_active(...)` | The agent writes down what it learns / the current focus. | After a decision, a gotcha, or finishing a chunk — so the next session inherits it. |
| `handoff()` | A structured end-of-session summary that seeds the next session. | **End of a work session**, before you close the chat. |
| `torsor consolidate` | Distills scattered journal notes into clean per-topic insight files. | **Weekly-ish housekeeping** — keeps memory from turning into noise. |
| `torsor clean` | Reclaims what torsor stopped needing: orphaned map notes, dead index rows, journals past retention. **Dry run by default.** | **Whenever `.torsor/` feels cluttered** — especially after renaming or deleting source files. |

### 🗺️ Understanding the codebase — *"the agent doesn't see how files connect"*
| Feature | What it does | Reach for it when… |
|---|---|---|
| `torsor map` | Builds a symbol map (functions/classes) **+ real reference edges** ("who calls what"). | **After big changes** (it auto-skips when nothing changed). Powers everything below. |
| `get_intent(topic)` | Surfaces the architecture + relevant existing symbols for a topic. | Before building a feature — *"what already exists around payments?"* |
| `torsor impact <symbol>` | Lists every caller of a symbol, across files — the **blast radius**. | **Before you let the agent change/rename a function** — see what breaks first. |
| `torsor find <query>` | **Fuzzy, frecency-ranked** search over files **and** mapped symbols (literal/regex too). | *"jump me to the file/function that does X"* — fast navigation without exact names. |
| `torsor export` | Writes a portable `llms.txt` + a GitHub-rendered **Mermaid** module diagram. | Onboarding a teammate/another tool, or you want an at-a-glance architecture picture. |

### 🛡️ Keeping your architecture — *"it quietly drifts from the plan"*
| Feature | What it does | Reach for it when… |
|---|---|---|
| `record_decision(...)` (ADRs) | Records an Architecture Decision — optionally with machine-readable **rules**. | You make a load-bearing call (*"the domain layer may not import the web layer"*). |
| `torsor practices --apply` | Adopts a **curated, research-backed best-practice pack** for your language (consensus linter/style rules, weighted toward documented AI failure modes) as one ADR the guard enforces. | **Project start**, or the first time you turn guardrails on — instant rules without writing them yourself. |
| `torsor guard` | Flags code that violates your ADR rules (`forbid_import`, layering, required seams…). | **Before every commit / in CI** (`--strict`). Catches drift the moment it appears. |
| `guard --update-baseline` | Grandfathers existing violations so `--strict` fails only on **new** drift. | **Adopting torsor on an existing/messy repo** — turn on CI without a wall of red. |
| `record_decision(..., supersedes=…)` | Marks an old ADR superseded so stale intent stops resurfacing in recall. | You change your mind — the new decision replaces the old cleanly. |

### 📦 Supply-chain safety — *"the AI imported a package that doesn't exist"*
| Feature | What it does | Reach for it when… |
|---|---|---|
| `torsor deps` | Flags imports that match **no** stdlib / installed / declared / first-party package — a possible **hallucinated dependency** ("slopsquatting"). | **Before `pip install`-ing what the agent suggested.** ~5–20% of AI imports don't exist; some are malware bait. Fully offline. |

### 🧭 The Coach — *"tell me what to fix, don't make me hunt"*
Run `torsor coach` (or it's pushed at session start). It's advisory, ranked, and **decays so it never nags**:
| Coach signal | What it tells you | Why it matters |
|---|---|---|
| `thin` / `stale` / `uncharted` | Your charter is still a template / active context is stale / modules aren't mapped. | Keeps the memory layer actually filled in and current. |
| `reuse` | *"`format_date()` already exists — reuse it instead of rewriting."* | Kills AI's #1 habit: duplicating code that already exists. |
| `hotspot` | The files with the most churn × complexity — **fix/test these first**. | Tells you *where* the risk concentrates, not just that risk exists. |
| `coupling` | Two files always change together but nothing links them — a **hidden dependency**. | Surfaces architecture the import graph can't see. |
| `regression` | A file's complexity **rose since your last `consolidate`** — review before it ossifies. | "New findings only" — alerts on what got *worse*, not absolute badness. |
| `phantom_dep` | An import resolves to no known package (see `torsor deps`). | Early warning on hallucinated dependencies. |

### 💸 Spending fewer (and cheaper) tokens — *"my agent keeps re-deriving the same things on the most expensive model"*
| Feature | What it does | Reach for it when… |
|---|---|---|
| `torsor commands` | A **learned command book** — record `test`/`build`/`lint`/`run` once; persisted in committed Markdown and shown in the primer. | The agent rediscovers *"how do I run the tests here?"* every session. Record it once, replay forever. |
| `torsor recipes` | Shows the **deterministic lookups you run most** (`recall`/`impact`/`get_intent`/…) with hit counts. | You want to see what recurs — the exact-answer work worth pushing to a cheap model. |
| `torsor models` | Sets a **cheap/smart model policy** and writes it into your agent's prompt file. | You want a cheap model doing the basic deterministic work and the frontier model only thinking/building. |

> **Rule of thumb:** start a session → `bootstrap_session`; before building → `recall` / `get_intent`; before changing a symbol → `impact`; before installing a suggested package → `deps`; before committing → `guard`; end of session → `handoff`; weekly → `consolidate` + skim `coach`.

## 💸 Token thrift — spend fewer, cheaper tokens

The most expensive tokens in agentic coding are **re-derivation**: the agent re-discovers how to run your tests, re-greps for callers, and re-reads files to answer questions that have an *exact, deterministic* answer — every session, usually on the most expensive model. torsor attacks this three ways. (torsor itself never calls an LLM — it makes the exact answers cheap to fetch and tells your harness how to route models.)

### 1. Learn the project's commands once — `torsor commands`
Stop the agent rediscovering *"how do I run the tests here?"* every session. Record it once; it lives in committed Markdown (`.torsor/commands.md`) and is shown in the primer, so every future session already knows it.
```bash
torsor commands --add 'test=uv run pytest' --note 'run the suite'
torsor commands --add 'lint=uv run ruff check src tests'
torsor commands --add 'build=uv build'
torsor commands              # list them
torsor commands --run test   # replay one from the repo root
```
Your agent calls `list_commands()` (or just reads the primer) and runs the exact command — no trial and error. The MCP server **records and lists** commands but never executes them; the agent runs them with its own shell.

### 2. See what recurs — `torsor recipes`
torsor records every deterministic lookup the agent makes (`recall`, `get_intent`, `find_files`, `impact`, `check_drift`, `check_dependencies`, `get_rules`) and how often:
```bash
torsor recipes
#  12×  recall 'auth flow'
#   8×  impact 'login'
#   5×  get_intent 'payments'
```
These are exact, deterministic answers the agent asks for over and over — prime candidates to run on a cheap model (next). It's *frequency tracking*, not a stale answer cache: the lookups stay exact-by-construction; torsor just learns which ones recur.

### 3. Route cheap vs smart models — `torsor models`
Declare which model does the basic deterministic work and which one thinks.
```bash
torsor models --cheap claude-haiku-4-5 --smart claude-opus-4-8
torsor models                      # show current tiers + the policy
```
The published policy, in plain terms:
- **Cheap model** → deterministic torsor lookups + command replays (`recall` · `get_intent` · `find_files` · `impact` · `get_rules` · `check_drift` · `check_dependencies` · `map_repo` · `consolidate` · `list_commands`). They return exact answers — no reasoning, no frontier model needed.
- **Smart model** → judgement & creation: designing architecture, writing/refactoring code, making decisions.

**App-agnostic — torsor only *declares* the policy; your tool *routes* by it, three universal ways:**

| Your app/harness | How it consumes the policy |
|---|---|
| **Any MCP client** (Claude Code, Cursor, Codex, Windsurf, Cline, …) | Calls the `get_model_policy()` tool (`as_json` for a parseable form) |
| **Any agent that reads a rules file** (AGENTS.md / CLAUDE.md / .cursorrules / …) | `torsor models --write AGENTS.md` injects a managed "Model routing" block the agent follows |
| **Any programmatic router / custom orchestrator** | `torsor models --json` (or `--write policy.json`) emits machine-readable JSON your code routes on |

```bash
torsor models --write AGENTS.md        # Markdown block — any prompt-reading agent
torsor models --json                   # machine-readable — pipe into any router
torsor models --write model-policy.json # …or write the JSON to a file
```

> **What torsor can and can't do:** it makes the exact answers cheap to fetch and *publishes* the routing policy in these portable forms. Whether a cheap model is actually used depends on your app supporting more than one model — a custom router or Claude Code subagents can route automatically; a single-model chat just gets the policy as guidance. Either way, the **command book + memory** already cut re-derivation regardless of model.

> **Put together:** the cheap model handles the dozens of recurring exact-answer lookups; the frontier model is reserved for genuine reasoning; and the command book + memory mean *neither* model re-derives what torsor already knows. That's the token — and dollar — saving.

## ✨ What's new

### v0.4 — token thrift *(spend fewer, cheaper tokens)*

| | Feature | Kills the failure mode | Try it |
|---|---|---|---|
| 🧰 | **Learned command book** | Agent re-derives how to test/build/lint every session | `torsor commands --add 'test=uv run pytest'` |
| 📊 | **Op-frequency recipes** | No visibility into what recurs (and could be cheaper) | `torsor recipes` |
| 💸 | **Cheap/smart model routing** | The frontier model does basic deterministic work | `torsor models --cheap … --smart …` |

Plus a **fuzzy + frecency finder** (`torsor find` / `find_files`) — fast navigation over files **and** mapped symbols (inspired by [dmtrKovalenko/fff](https://github.com/dmtrKovalenko/fff), pure-Python, no daemon). See [Token thrift](#-token-thrift--spend-fewer-cheaper-tokens).

### v0.3 — the resilience release *(supply-chain + blast-radius + hidden coupling)*

Four research-driven features (from deep research into [documented vibe-coding failure modes](docs/superpowers/specs/2026-06-10-torsor-v0.3-resilience-design.md) — hallucinated deps, cross-file cascades, hidden coupling, review fatigue), each hardened by adversarial review:

| | Feature | Kills the failure mode | Try it |
|---|---|---|---|
| 📦 | **Slopsquatting guard** | AI imports a non-existent package (USENIX '25: ~5–21% don't exist) | `torsor deps` |
| 🔎 | **Impact analysis** | Changing a symbol silently cascades across files | `torsor impact <symbol>` |
| 🔗 | **Temporal-coupling recs** | Hidden dependencies the import graph can't see | `torsor coach` |
| 📉 | **Complexity-trend regressions** | Review fatigue — alert only on what got *worse* | `torsor coach` after `consolidate` |

### v0.2 — the intelligence release

Twelve improvements distilled from deep research into the best memory / repo-map / architecture-guard / code-health tools, then hardened by an adversarial review. All **dependency-free, deterministic, and offline-testable** — every invariant intact.

| | Improvement | What it buys you | Inspired by |
|---|---|---|---|
| 🔎 | **Contextual breadcrumbs** | Indexes tier·path·title with each note so a query for situating terms finds it (snippets stay byte-identical) | Anthropic Contextual Retrieval |
| 🔎 | **Section-aware snippets** | Recall returns the *densest* matching section, not the first keyword hit | — |
| 🔎 | **Importance decay** | Frequently-recalled notes float up; episodic noise sinks; charter/architecture never decay | mem0, Reflexion |
| 🔎 | **MMR diversity + budget marker** | Near-duplicate notes demoted; truncation made explicit | MMR (Carbonell & Goldstein) |
| 🗺️ | **AST reference edges** | Honest "who references what" + ref counts (no more substring counting of comments) | Aider repo map, Serena, SCIP |
| 🗺️ | **Fingerprint skip** | `torsor map` is instant when nothing changed | Continue.dev, Cursor indexing |
| 🗺️ | **`torsor export`** | Portable `llms.txt` + a GitHub-rendered **Mermaid** module diagram | llms.txt, DeepWiki |
| 🛡️ | **Layering & seam rules** | `forbid_layer_import` + `require_import` express real architecture, not just deny-lists | ArchUnit, dependency-cruiser, import-linter |
| 🛡️ | **Severity + `--json`** | Per-rule severity, machine-readable findings, threshold-gated CI | ast-grep, dependency-cruiser |
| 🛡️ | **Drift baseline** | `--strict` fails only on *new* drift — adoptable on a brownfield repo | ArchUnit FreezingArchRule, SonarQube |
| 🧭 | **Churn × complexity hotspots** | The Coach says *where* to refactor/test first | CodeScene, SonarQube |
| 🧭 | **ADR supersedes** | Superseded decisions stop resurfacing in recall | mem0, Zep/Graphiti |

→ Full per-item notes in the [CHANGELOG](CHANGELOG.md) and the [v0.2 design spec](docs/superpowers/specs/2026-06-02-torsor-v0.2-intelligence-design.md).

## 📦 Install

`torsor-helper` is a small, local-first Python package (Python ≥ 3.11). *(Full walkthrough incl. troubleshooting: [docs/how-to-install.md](docs/how-to-install.md).)*

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

Then put your standing rules where the agent reads them for free:

```bash
torsor rules --write AGENTS.md     # or CLAUDE.md — refresh any time you record a new ADR
```

`torsor rules` distills your charter's non-negotiable principles plus every machine-readable ADR rule into a compact (~600-token, budget-capped) digest, written into a managed block in your agent's prompt file. The agent sees the constraints **at prompt time — no tool calls, no rediscovery, no burned context** — and `torsor guard` still enforces the same rules deterministically in CI. Re-running replaces the block, never duplicates it.

## 🔌 Connect your agent (Claude Code, Codex, Cursor, …)

torsor-helper is a standard **MCP stdio server** — the command is `torsor mcp`. Point any MCP client at it. `torsor init --client <name>` prints exact, copy-paste config for your tool.

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

### Google Antigravity
Agent panel → settings → **MCP Servers** → *Manage* opens `mcp_config.json` — paste the standard block (`torsor init --client antigravity`):
```json
{ "mcpServers": { "torsor-helper": { "command": "torsor", "args": ["mcp"] } } }
```

### Everything else — one command prints your client's exact config + where it goes
```bash
torsor init --client <name>
```

| Client | `--client` | Config goes in |
|---|---|---|
| Windsurf | `windsurf` | `~/.codeium/windsurf/mcp_config.json` (Settings → Cascade → MCP) |
| Trae | `trae` | AI chat → Settings → MCP → Add manually |
| Cline / Roo Code | `cline` / `roo` | extension → MCP Servers → Configure |
| Claude Desktop | `claude-desktop` | `claude_desktop_config.json` (Settings → Developer) |
| Gemini CLI | `gemini` | `~/.gemini/settings.json` or project `.gemini/settings.json` |
| GitHub Copilot CLI | `copilot-cli` | `~/.copilot/mcp-config.json` (or `/mcp add` in the CLI) |
| Zed | `zed` | `settings.json` (`context_servers` shape — snippet handles it) |
| JetBrains AI / Junie | `jetbrains` | Settings → Tools → AI Assistant → MCP → Add |
| Continue | `continue` | `.continue/config.yaml` (YAML shape — snippet handles it) |
| OpenCode | `opencode` | `opencode.json` (its own `mcp` shape — snippet handles it) |
| Amp | `amp` | VS Code `settings.json` under `amp.mcpServers` |
| Goose | `goose` | `~/.config/goose/config.yaml` (or `goose configure`) |
| Kiro | `kiro` | `.kiro/settings/mcp.json` |
| Warp | `warp` | Settings → AI → Manage MCP servers |

> **Note:** the config uses `command: "torsor"`, which requires the `torsor` command on your PATH (`uv tool install` / `pipx install`). Running ephemerally instead? Use `"command": "uvx", "args": ["torsor-helper", "mcp"]`.

## 🛠️ Usage

*(Full day-to-day guide — first hour, daily loop, rule kinds, CI recipes, FAQ: [docs/how-to-use.md](docs/how-to-use.md).)*

### CLI

| Command | What it does |
|---|---|
| `torsor init [--write] [--client <name>]` | Scaffold `.torsor/`; `--write` emits `.mcp.json`; `--client` prints that client's config |
| `torsor --version` | Print the installed torsor-helper version |
| `torsor mcp [--http --host --port]` | Run the MCP server (stdio by default; `--http` for a shared service) |
| `torsor doctor` | Verify the project is healthy |
| `torsor index [--full]` | Build/refresh the derived search index |
| `torsor map [--force]` | Generate the repository symbol map + reference edges (skips when unchanged; `--force` to re-scan) |
| `torsor impact <symbol>` | Show the blast radius of a symbol — who references it, across files |
| `torsor find <query> [--mode] [--files-only/--symbols-only]` | Fuzzy + frecency search over files and mapped symbols (fuzzy/literal/regex) |
| `torsor export` | Write a portable `llms.txt` + a Mermaid module-dependency diagram into the map |
| `torsor practices [<lang>] [--apply]` | List/adopt curated best-practice packs (python · javascript · typescript · go · rust · agent) — `--apply` records an ADR the guard enforces |
| `torsor primer [--write <file>] [--tokens N]` | **Token saver:** budgeted prompt-time project primer (charter + architecture + map + token-efficiency habits) — zero discovery tool-calls per session |
| `torsor update [--print-only]` | Update the torsor CLI itself (detects uv tool / pipx / pip installs) |
| `torsor rules [--write <file>] [--scoped]` | Print a compact agent-rules digest (charter principles + ADR rules); `--write` maintains a managed block in `AGENTS.md`/`CLAUDE.md`; `--scoped` writes one path-scoped Claude Code rule file per ADR under `.claude/rules/torsor/` — prompt-time rules at zero tool-call cost |
| `torsor deps [files…] [--strict]` | Flag imports resolving to no known package — possible hallucinated dependencies (offline) |
| `torsor guard [files…] [--strict] [--severity <lvl>] [--json] [--update-baseline]` | Flag ADR-rule violations; `--strict` fails CI on **new** drift; `--json` for machine-readable findings |
| `torsor coach [context] [--dismiss <key>]` | Health + reuse + **hotspot** + **coupling** + **regression** + **phantom-dep** recommendations |
| `torsor consolidate` | Self-improving pass: mine journal → insight notes, reindex, snapshot complexity, report duplicates |
| `torsor clean [--apply] [--deep]` | Garbage-collect derived artefacts: orphaned map notes, dead index rows (+VACUUM), expired journals; `--deep` drops the whole index. Dry run unless `--apply` |
| `torsor commands [--add 'name=cmd'] [--run name]` | Record & replay project commands (test/build/lint) so agents don't re-derive them |
| `torsor recipes` | The deterministic lookups you run most — candidates to route to the cheap model |
| `torsor models [--cheap … --smart …] [--write AGENTS.md\|policy.json] [--json]` | Set the cheap/smart model policy; publish it as a prompt block, JSON, or via MCP — app-agnostic |

### MCP tools (what the agent calls)

| Tool | What it does |
|---|---|
| `bootstrap_session()` | Budgeted summary of the whole pyramid at session start (+ a hygiene digest) |
| `recall(query)` | Hybrid search over memory + wiki (vector + FTS5, fused via RRF) |
| `remember(content)` · `update_active(...)` | Self-editing memory the agent maintains as it works |
| `handoff()` | Structured end-of-session summary → seeds the next session |
| `get_intent(topic?)` · `map_repo(force?)` · `impact(symbol)` | Surface architecture + symbols relevant to a change; show a symbol's caller blast radius |
| `find_files(query, mode?)` | Fuzzy, frecency-ranked search over repo files + mapped symbols (fuzzy/literal/regex) |
| `record_decision(..., supersedes?)` · `check_drift(..., as_json?, new_only?)` | Record ADRs (that become rules); flag changes that violate intent |
| `get_rules()` | The standing constraints (principles + ADR rules) as one compact digest — load once per session |
| `get_primer(max_tokens?)` · `list_practices(lang?)` · `adopt_practices(lang)` | Token-saving project primer; list/adopt curated best-practice packs as guard-enforced ADRs |
| `check_dependencies(files?)` · `export()` | Flag hallucinated imports (slopsquatting); portable `llms.txt` + Mermaid diagram |
| `record_command(...)` · `list_commands()` · `recipes()` | The learned command book + the most-repeated deterministic lookups (token thrift) |
| `get_model_policy(as_json?)` | The cheap/smart model-routing policy to follow — do basic lookups on the cheap model (`as_json` for a parseable form) |
| `recommend(context?)` · `consolidate()` | The Coach (health · reuse · hotspots · coupling · regressions · phantom-deps); self-improving maintenance |
| `clean(apply?, deep?)` | Reclaim orphaned map notes, dead index rows and expired journals — dry run unless `apply` |

### A typical loop
1. **Once:** `torsor init --write`, fill in `charter.md` + `architecture/`, commit `.torsor/`; `torsor rules --write AGENTS.md` so the rules live in the prompt.
2. **Each session:** the agent calls `bootstrap_session()` → gets your charter, architecture, active state, recent memory, and a hygiene nudge or two.
3. **While working:** it `recall()`s prior decisions, `get_intent()` before changes, and `remember()`s what it learns.
4. **Before a commit:** `check_drift()` flags anything that violates your ADR rules.
5. **End of session:** `handoff()` writes a summary the next session resumes from.
6. **Periodically:** `torsor coach` for health + reuse nudges; `torsor consolidate` to distill journal into insights; `torsor clean` to see what's become dead weight (then `--apply`).

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
├─ models.py        # Pydantic models: Note, Symbol, SymbolEdge, Rule, Violation, Recommendation, …
├─ paths.py         # .torsor/ layout            store.py     # Markdown I/O (frontmatter + wikilinks)
├─ templates.py     # seed pyramid               budget.py    # token budgeting
├─ config.py        # torsor.toml                db.py        # SQLite: FTS5 + vectors + wiki edges + symbols + symbol_edges
├─ embeddings.py    # FastEmbed | Hashing        indexer.py   # incremental reindex + contextual breadcrumbs
├─ recall.py        # keyword fallback           search.py    # hybrid RRF + importance decay + MMR
├─ snippets.py      # section-aware snippets      cartographer.py  # stdlib-ast symbols + reference edges
├─ guard.py         # ADR rules → drift detection baseline.py  # committed drift baseline (ratchet)
├─ export.py        # llms.txt + Mermaid diagram  deps.py      # offline slopsquatting guard
├─ coach/           # health · recommender · report · state · mining · hotspots · coupling · trend
├─ operations.py    # orchestration incl. impact() (the tested core)
├─ server.py        # FastMCP adapter            cli.py       # Typer CLI
```

Everything is **dogfooded**: this repo has its own `.torsor/` with real ADRs whose layering rules `torsor guard` enforces, a `torsor map` of its own symbols **and reference edges**, and a clean `torsor coach` / `torsor deps` run. **235 tests, lint-clean**, every feature offline-testable.

## 📍 Status & roadmap

**v0.4 shipped — 328 tests, lint-clean, dogfooded.** The 6-phase foundation, the intelligence release (v0.2), the resilience release (v0.3), and the token-thrift release (v0.4).

**Foundation (v0.1):**
- [x] **Foundation** · pyramid scaffold, `init`, MCP server, the five memory tools
- [x] **Index** · SQLite (FTS5 + wiki-link graph) + local embeddings, incremental indexer, hybrid RRF recall
- [x] **Map** · stdlib-`ast` cartographer + symbol inventory + `get_intent` / `map_repo`
- [x] **Guard** · ADRs carry machine-readable rules; deterministic drift detection (`check_drift`)
- [x] **Consolidation** · `torsor consolidate` mines journal entries into curated insight notes
- [x] **Coach** · hygiene + best-practice recommendations, pushed at session start
- [x] **HTTP/team transport** · `torsor mcp --http`

**Intelligence release (v0.2):**
- [x] **Retrieval** · contextual breadcrumbs · section-aware snippets · importance decay · MMR diversity
- [x] **Map** · real AST reference edges + honest ref counts · fingerprint skip · `torsor export` (llms.txt + Mermaid)
- [x] **Guard** · layering/seam rule kinds · severity + `--json` · committed drift baseline (CI ratchet)
- [x] **Coach** · churn×complexity hotspots · ADR supersedes

**Resilience release (v0.3):**
- [x] **Supply chain** · offline slopsquatting guard (`torsor deps`) — flag hallucinated dependencies
- [x] **Blast radius** · impact analysis (`torsor impact`) — who-references a symbol across files
- [x] **Hidden coupling** · temporal-coupling coach recs from git co-change
- [x] **Never-nag** · complexity-trend "new findings only" regressions

**Token-thrift release (v0.4):**
- [x] **Navigation** · fuzzy + frecency finder (`torsor find` / `find_files`) over files + mapped symbols
- [x] **Command book** · `torsor commands` — record & replay project commands (no re-derivation)
- [x] **Recipes** · `torsor recipes` — learn which deterministic lookups recur
- [x] **Model routing** · `torsor models` — cheap/smart policy, app-agnostic (MCP · prompt block · JSON), `--client` publish

**Planned fast-follows (v0.7):** multi-language map (tree-sitter) for JS/TS · sampling-based *semantic* drift guard · weaving `impact`/`deps` warnings into `check_drift` and pre-commit flows.

## 🧪 Built with

FastMCP · Typer · Pydantic · PyYAML · SQLite (FTS5) · NumPy · stdlib `ast` — *local-first, no API key required.* Optional `fastembed` extra for semantic embeddings. The repo map is Python-only today (multi-language is planned); the drift guard is deterministic (ADR rules → AST/regex).

## 📚 Design & prior art

Full design + every phase plan live in [`docs/superpowers/`](docs/superpowers/) (including the [v0.2 design spec](docs/superpowers/specs/2026-06-02-torsor-v0.2-intelligence-design.md)). torsor-helper stands on the shoulders of [Cline Memory Bank](https://docs.cline.bot/prompting/cline-memory-bank), [mem0/OpenMemory](https://mem0.ai/openmemory), [Letta/MemGPT](https://docs.letta.com/), [Zep/Graphiti](https://github.com/getzep/graphiti), [basic-memory](https://github.com/basicmachines-co/basic-memory), [cognee](https://github.com/topoteretes/cognee), [Aider's repo map](https://aider.chat/docs/repomap.html), [Serena](https://github.com/oraios/serena), [CodeScene](https://codescene.com/), [ArchUnit](https://www.archunit.org/) / [dependency-cruiser](https://github.com/sverweij/dependency-cruiser), [Anthropic Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval), [llms.txt](https://llmstxt.org/), and [GitHub spec-kit](https://github.com/github/spec-kit).

## 🤝 Contributing & releasing

`uv run --extra dev pytest` (235 tests) · `uv run --with ruff ruff check src tests`. Releasing: see [PUBLISHING.md](PUBLISHING.md).

## License

[MIT](LICENSE) © Marko Tiosavljevic.

---

<div align="center"><sub>Author: <a href="https://mtiosavljevic.com">Marko Tiosavljevic</a> · <a href="https://imbamarketing.com">Imba Marketing</a></sub><br>
<sub>Built with the <a href="https://claude.com/claude-code">Claude Code</a> superpowers workflow — brainstorm → spec → plan → TDD → review.</sub></div>
