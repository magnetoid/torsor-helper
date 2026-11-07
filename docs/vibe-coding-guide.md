# Vibe-coding with torsor-helper

**Vibe coding** = building fast by describing what you want to an AI agent and letting it write the code. It's fantastic for momentum and brutal for memory: the agent forgets your decisions between sessions, drifts from your architecture, rebuilds things that already exist, and occasionally imports packages that don't exist. torsor-helper is a small local MCP server for one developer and an agent: **project memory that lives in the repo** (not in one tool on one machine), a **guard** that enforces your rules as a hook, a **code map** with blast radius, an offline **dependency check**, and a **coach** — so you keep the speed without the chaos.

This guide is the practical "how do I actually use it while coding" walkthrough. For setup see [how-to-install.md](how-to-install.md); for the full reference see [how-to-use.md](how-to-use.md); for the design rationale see the [README](../README.md).

**Contents:** [Why vibe coding needs this](#why-vibe-coding-needs-this) · [90-second setup](#90-second-setup) · [The loop](#the-vibe-coding-loop) · [Make it self-driving](#make-it-self-driving) · [Greenfield vs existing repo](#greenfield-vs-existing-repo) · [Spending fewer tokens](#spending-fewer-tokens) · [A worked session](#a-worked-session) · [Answers (FAQ)](#answers-faq)

---

## Why vibe coding needs this

| What goes wrong when you vibe-code | What it costs you | torsor's answer |
|---|---|---|
| New chat starts from zero; long chats forget mid-stream | You re-explain the project every session | `bootstrap_session` + the committed pyramid + `handoff` |
| You switch between Claude Code, Codex and Cursor | Each has its own memory, on this machine only | `.torsor/` is in the repo — one memory, every agent, every clone |
| Agent rebuilds a helper you already have | Duplicated, divergent code | `recall` / `get_intent` before building |
| Agent silently breaks the architecture you set | Bugs, layering rot, rejected patterns return | ADR rules + `guard` — as a hook on every edit, `--strict` in CI |
| Agent renames/regenerates a function used elsewhere | Far-off callers break | `impact <symbol>` shows the blast radius first |
| Agent imports a package that doesn't exist | Supply-chain risk ("slopsquatting") | `deps` — offline check |
| You burn tokens on trivial re-derivation | $$$ | the primer/rules in your prompt + the command book |

The throughline: **the expensive part of vibe coding is re-derivation.** torsor remembers the answers so neither you nor the model has to reconstruct them.

## 90-second setup

```bash
cd your-project
torsor init --write            # scaffold .torsor/ + write .mcp.json so your agent auto-detects it
torsor doctor                  # sanity check
```

Then fill the two files that matter most (or ask your agent to draft them — *"read the codebase and fill in .torsor/charter.md and .torsor/architecture/system-patterns.md"*):

- **`.torsor/charter.md`** — what you're building, why, and the principles you refuse to break.
- **`.torsor/architecture/system-patterns.md`** — layering, conventions, the patterns in use.

Put the rules and a primer into your agent's prompt file so they cost **zero tool calls**, then commit:

```bash
torsor rules  --client claude-code   # writes a managed block into CLAUDE.md (or --client cursor → AGENTS.md, etc.)
torsor primer --client claude-code
torsor map                           # build the symbol map + reference edges
torsor hooks install                 # session-start digest, edit gate, auto-handoff (Claude Code + git)
git add .torsor && git commit -m "Add project memory"
```

> `--client <name>` drops the block into that tool's conventional file automatically (CLAUDE.md for Claude Code, GEMINI.md for Gemini, AGENTS.md for everything else). Prefer an exact path? Use `--write AGENTS.md`.

## The vibe-coding loop

Five habits. The agent does most of them via MCP tools; you can run any of them from the CLI.

1. **Start the session →** the agent calls `bootstrap_session()` — a budgeted summary of charter → architecture → active state → recent memory + a short Coach nudge. No blank-slate start.
2. **Before building →** `recall("how does auth work here?")` and `get_intent("payments")` surface prior decisions and existing symbols, so the agent *extends* instead of *duplicating*.
3. **Before changing a shared function →** `impact("charge_card")` lists every caller across files. One regenerated symbol silently breaking callers is the classic vibe-coding bug; this prevents it.
4. **Before committing →** `torsor guard` flags anything that violates your ADR rules; `torsor deps` flags hallucinated imports. With hooks installed, the guard already ran against each proposed edit *before* it landed. Wire `torsor guard --strict` into CI to fail only on *new* drift.
5. **End the session →** `handoff(summary=…, next_steps=…)` writes the note the next session resumes from. **This is the single highest-value habit** — it's what makes tomorrow's session continue instead of restart.

As the agent learns things, it should `remember("we use WAL mode for concurrent CLI+server", kind="learning")` and keep `update_active(...)` current. Weekly-ish: `torsor coach` for nudges, `torsor clean` to reclaim dead artefacts.

## Make it self-driving

You don't want to *remember* to use torsor — you want the agent to do it automatically. Put the instruction in the prompt file once:

```bash
torsor primer --client claude-code   # adds the project primer + token-efficiency habits
torsor rules  --client claude-code   # adds the standing rules
```

The primer already includes habits like *"call `bootstrap_session()` once at session start; `recall`/`get_intent` before reading files; `impact` instead of repo-wide grep; `handoff()` at session end."* Add a line of your own to CLAUDE.md/AGENTS.md if you want it stricter, e.g.:

> Always call `bootstrap_session()` at the start of a session and `handoff()` before you stop. Before writing a new function, `recall`/`get_intent` to check it doesn't already exist.

## Greenfield vs existing repo

**Greenfield (new project):** charter + system-patterns are your *intentions*. Write them first — they steer every session. Record decisions as you make them (`record_decision(...)` with a `rule` so the guard enforces it from day one).

**Existing/messy repo:** map it (`torsor map`), then let the agent draft the charter/patterns from the code. Record the rules you actually care about and **grandfather the mess** so CI isn't a wall of red:

```bash
torsor guard --update-baseline      # accept today's violations as the baseline
torsor guard --strict               # from now on, CI fails only on NEW drift
```

## Spending fewer tokens

Two levers, both local, both zero tool-call cost once set up:

1. **Prompt blocks — orientation and rules the agent reads for free.** `torsor primer --client claude-code` and `torsor rules --client claude-code` write budgeted managed blocks into the prompt file. The agent doesn't spend tool calls rediscovering what the project is or which rules hold.

2. **Command book — stop re-deriving project commands.**
   ```bash
   torsor commands --add test 'uv run pytest' --note 'run the suite'
   torsor commands --add lint 'ruff check src tests'
   ```
   Recorded once, shown in the primer, replayable with `torsor commands --run test`. The agent never rediscovers "how do I run the tests here?".

## A worked session

> **You:** "Add rate limiting to the payments endpoint."

1. Agent calls `bootstrap_session()` → already knows this is a FastAPI app, that the domain layer must not import the web layer (ADR 0002), and that last session added the `payments` router.
2. Agent calls `get_intent("rate limit")` → finds you already have `app/util/throttle.py`. It reuses it instead of writing a new limiter.
3. Agent edits `payments.py`. Before regenerating `charge()`, it calls `impact("charge")` → sees 3 callers in `billing/` and adjusts them too. The edit-gate hook checks each Write against ADR 0002 as it happens.
4. You ask it to commit. `torsor guard` runs → clean (no layering violation). `torsor deps` → the `slowapi` import it added is real and declared.
5. Agent calls `remember("payments uses slowapi limiter via app/util/throttle", kind="learning")` and `handoff(summary="added rate limiting to /payments", next_steps="add tests for the 429 path")`.

Next session, `bootstrap_session()` surfaces that handoff — the agent picks up exactly where it left off, including the "add tests for the 429 path" todo.

## Answers (FAQ)

**Do I need an API key or internet?** No. Everything is local and offline. The optional `embeddings` extra downloads one small model once for better semantic recall; without it, recall uses a deterministic offline fallback.

**Where does my data live? Is it safe?** In `.torsor/` as plain Markdown you own and commit to git. Nothing leaves your machine. The SQLite index under `.torsor/.index/` is derived and git-ignored.

**Does it slow the agent down?** The opposite — one `recall`/`get_intent` call replaces re-reading many files. `torsor map` skips entirely when nothing changed; recall reindexes incrementally.

**How does it actually save tokens?** Three ways: (1) the primer/rules sit in the prompt file, so the agent doesn't spend tool calls rediscovering them; (2) one exact-answer lookup (`recall`, `impact`, `get_intent`) replaces exploratory file-reading; (3) the command book means no session re-derives how to test or build.

**My index looks stale / broke.** Delete `.torsor/.index/` and run `torsor index` (or just let the next `recall` rebuild it). It's always disposable; Markdown is the source of truth.

**Can I edit the Markdown by hand?** Yes — that's the point. Obsidian works too (`[[wikilinks]]` are first-class). Malformed frontmatter degrades gracefully and never breaks recall.

**The Coach is nagging about one thing.** `torsor coach --dismiss <key>` (the key prints with each recommendation). Recommendations also decay on their own so they never nag.

**Does the agent run my recorded commands automatically?** No — the MCP server *records and lists* commands but never executes them. The agent runs them with its own shell (you stay in control); only the `torsor commands --run` CLI executes.

**What goes in git?** `.torsor/` yes (it's your project's memory + committed config like `baseline.json`, `commands.md`). `.torsor/.index/` no — the scaffolded `.gitignore` handles it.

**Does it work with my tool?** If it speaks MCP, yes. `torsor init --client <name>` prints the exact config for Claude Code, Cursor, Codex, VS Code/Copilot and Gemini CLI; `--client other` prints the standard `mcpServers` block every other client accepts. Even tools that don't speak MCP can read the Markdown blocks torsor writes into AGENTS.md/CLAUDE.md.
