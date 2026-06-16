# Vibe-coding with torsor-helper

**Vibe coding** = building fast by describing what you want to an AI agent and letting it write the code. It's fantastic for momentum and brutal for memory: the agent forgets your decisions between sessions, drifts from your architecture, rebuilds things that already exist, and occasionally imports packages that don't exist. torsor-helper is the layer that gives the agent a **persistent brain, guardrails, and a coach** — so you keep the speed without the chaos.

This guide is the practical "how do I actually use it while coding" walkthrough. For setup see [how-to-install.md](how-to-install.md); for the full reference see [how-to-use.md](how-to-use.md); for the design rationale see the [README](../README.md).

**Contents:** [Why vibe coding needs this](#why-vibe-coding-needs-this) · [90-second setup](#90-second-setup) · [The loop](#the-vibe-coding-loop) · [Make it self-driving](#make-it-self-driving) · [Greenfield vs existing repo](#greenfield-vs-existing-repo) · [Spending fewer tokens](#spending-fewer-and-cheaper-tokens) · [A worked session](#a-worked-session) · [Answers (FAQ)](#answers-faq)

---

## Why vibe coding needs this

| What goes wrong when you vibe-code | What it costs you | torsor's answer |
|---|---|---|
| New chat starts from zero; long chats forget mid-stream | You re-explain the project every session | `bootstrap_session` + the pyramid + `handoff` |
| Agent rebuilds a helper you already have | Duplicated, divergent code | `recall` / `get_intent` / `find` + the Coach's `reuse` rec |
| Agent silently breaks the architecture you set | Bugs, layering rot, rejected patterns return | ADR rules + `guard` (advisory, or `--strict` in CI) |
| Agent renames/regenerates a function used elsewhere | Far-off callers break | `impact <symbol>` shows the blast radius first |
| Agent imports a package that doesn't exist | Supply-chain risk ("slopsquatting") | `deps` — offline check |
| You burn frontier-model tokens on trivial lookups | $$$ | the primer/rules in your prompt + `models` routing |

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
git add .torsor && git commit -m "Add project memory"
```

> `--client <name>` drops the block into that tool's conventional file automatically (CLAUDE.md for Claude Code, GEMINI.md for Gemini, AGENTS.md for everything else). Prefer an exact path? Use `--write AGENTS.md`.

## The vibe-coding loop

Five habits. The agent does most of them via MCP tools; you can run any of them from the CLI.

1. **Start the session →** the agent calls `bootstrap_session()` — a budgeted summary of charter → architecture → active state → recent memory + a short Coach nudge. No blank-slate start.
2. **Before building →** `recall("how does auth work here?")` and `get_intent("payments")` surface prior decisions and existing symbols, so the agent *extends* instead of *duplicating*. Use `find("ratelimit")` to jump straight to a file/symbol.
3. **Before changing a shared function →** `impact("charge_card")` lists every caller across files. One regenerated symbol silently breaking callers is the classic vibe-coding bug; this prevents it.
4. **Before committing →** `torsor guard` flags anything that violates your ADR rules; `torsor deps` flags hallucinated imports. Wire `torsor guard --strict` into CI to fail only on *new* drift.
5. **End the session →** `handoff(summary=…, next_steps=…)` writes the note the next session resumes from. **This is the single highest-value habit** — it's what makes tomorrow's session continue instead of restart.

As the agent learns things, it should `remember("we use WAL mode for concurrent CLI+server", kind="learning")` and keep `update_active(...)` current. Weekly-ish: `torsor coach` for nudges, `torsor consolidate` to distill the journal into clean insight notes.

## Make it self-driving

You don't want to *remember* to use torsor — you want the agent to do it automatically. Put the instruction in the prompt file once:

```bash
torsor primer --client claude-code   # adds the project primer + token-efficiency habits
torsor rules  --client claude-code   # adds the standing rules
```

The primer already includes habits like *"call `bootstrap_session()` once at session start; `recall`/`get_intent` before reading files; `impact` instead of repo-wide grep; `handoff()` at session end."* Add a line of your own to CLAUDE.md/AGENTS.md if you want it stricter, e.g.:

> Always call `bootstrap_session()` at the start of a session and `handoff()` before you stop. Before writing a new function, `recall`/`get_intent` to check it doesn't already exist.

## Greenfield vs existing repo

**Greenfield (new project):** charter + system-patterns are your *intentions*. Write them first — they steer every session. Record decisions as you make them (`record_decision(...)` with a `rule` so the guard enforces it). Adopt a best-practice pack for instant guardrails: `torsor practices python --apply`.

**Existing/messy repo:** map it (`torsor map`), then let the agent draft the charter/patterns from the code. Adopt rules gradually and **grandfather the mess** so CI isn't a wall of red:

```bash
torsor practices python --apply
torsor guard --update-baseline      # accept today's violations as the baseline
torsor guard --strict               # from now on, CI fails only on NEW drift
```

## Spending fewer (and cheaper) tokens

Three levers, all optional, all local:

1. **Command book — stop re-deriving project commands.**
   ```bash
   torsor commands --add 'test=uv run pytest' --note 'run the suite'
   torsor commands --add 'lint=ruff check src tests'
   ```
   Recorded once, shown in the primer, replayable with `torsor commands --run test`. The agent never rediscovers "how do I run the tests here?".

2. **Recipes — see what recurs.** `torsor recipes` lists the deterministic lookups the agent repeats most (`recall`/`impact`/`get_intent`/…). Those are exact-answer calls — prime candidates for a cheap model.

3. **Model routing — cheap model for basic work, smart model for thinking.**
   ```bash
   torsor models --cheap claude-haiku-4-5 --smart claude-opus-4-8
   torsor models --client claude-code    # publish the routing policy into the prompt file
   torsor models --json                  # …or machine-readable, for a custom router
   ```
   torsor *declares* the policy (deterministic lookups + command replays → cheap; design/code/decisions → smart); your harness routes by it. Whether a cheap model is actually used depends on your tool supporting more than one model — but the command book + memory cut re-derivation regardless.

## A worked session

> **You:** "Add rate limiting to the payments endpoint."

1. Agent calls `bootstrap_session()` → already knows this is a FastAPI app, that the domain layer must not import the web layer (ADR 0002), and that last session added the `payments` router.
2. Agent calls `get_intent("rate limit")` and `find("limiter")` → finds you already have `app/util/throttle.py`. It reuses it instead of writing a new limiter. *(Coach would have nagged `reuse` otherwise.)*
3. Agent edits `payments.py`. Before regenerating `charge()`, it calls `impact("charge")` → sees 3 callers in `billing/` and adjusts them too.
4. You ask it to commit. `torsor guard` runs → clean (no layering violation). `torsor deps` → the `slowapi` import it added is real and declared. 
5. Agent calls `remember("payments uses slowapi limiter via app/util/throttle", kind="learning")` and `handoff(summary="added rate limiting to /payments", next_steps="add tests for the 429 path")`.

Next session, `bootstrap_session()` surfaces that handoff — the agent picks up exactly where it left off, including the "add tests for the 429 path" todo.

## Answers (FAQ)

**Do I need an API key or internet?** No. Everything is local and offline. The optional `embeddings` extra downloads one small model once for better semantic recall; without it, recall uses a deterministic offline fallback.

**Where does my data live? Is it safe?** In `.torsor/` as plain Markdown you own and commit to git. Nothing leaves your machine. The SQLite index under `.torsor/.index/` is derived and git-ignored.

**Does it slow the agent down?** The opposite — one `recall`/`get_intent` call replaces re-reading many files. `torsor map` skips entirely when nothing changed; recall reindexes incrementally.

**How does it actually save tokens?** Three ways: (1) the primer/rules sit in the prompt file, so the agent doesn't spend tool calls rediscovering them; (2) one exact-answer lookup replaces exploratory file-reading; (3) the model-routing policy lets a cheap model handle the recurring deterministic lookups.

**My index looks stale / broke.** Delete `.torsor/.index/` and run `torsor index` (or just let the next `recall` rebuild it). It's always disposable; Markdown is the source of truth.

**Can I edit the Markdown by hand?** Yes — that's the point. Obsidian works too (`[[wikilinks]]` are first-class). Malformed frontmatter degrades gracefully and never breaks recall.

**The Coach is nagging about one thing.** `torsor coach --dismiss <key>` (the key prints with each recommendation). Recommendations also decay on their own so they never nag.

**Does the agent run my recorded commands automatically?** No — the MCP server *records and lists* commands but never executes them. The agent runs them with its own shell (you stay in control); only the `torsor commands --run` CLI executes.

**Which model should be "cheap" vs "smart"?** Cheap = a small fast model for deterministic torsor lookups and command replays (no reasoning needed). Smart = your best model for design, writing/refactoring code, and decisions. See `torsor models`.

**What goes in git?** `.torsor/` yes (it's your project's memory + committed config like `baseline.json`, `commands.md`). `.torsor/.index/` no — the scaffolded `.gitignore` handles it.

**Does it work with my tool?** If it speaks MCP (Claude Code, Cursor, Codex, Windsurf, Cline, VS Code/Copilot, Zed, Gemini, …), yes — `torsor init --client <name>` prints the exact config. Even tools that don't can read the Markdown blocks torsor writes into AGENTS.md/CLAUDE.md.
