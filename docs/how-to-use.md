# How to use torsor-helper

This is the practical, day-to-day reference. New to vibe-coding with torsor? Start with the [**Vibe-coding guide**](vibe-coding-guide.md). For setup, see [how-to-install.md](how-to-install.md); for the design rationale, see the [README](../README.md).

**Contents:** [Mental model](#the-mental-model-60-seconds) · [First hour](#the-first-hour-set-up-your-projects-memory) · [Daily loop](#the-daily-loop) · [Architecture rules](#keeping-your-architecture-adrs--rules--guard) · [Codebase map](#understanding-the-codebase-map--intent--impact) · [Dependency safety](#dependency-safety) · [The Coach](#the-coach--housekeeping) · [CLI reference](#cli-reference) · [MCP tool reference](#mcp-tool-reference) · [FAQ](#faq)

## The mental model (60 seconds)

Your project's memory is **plain Markdown you own**, under `.torsor/`, in five tiers ordered by stability:

| Tier | Folder | Holds | Changes |
|---|---|---|---|
| T0 Charter | `charter.md` | what & why, non-negotiable principles | rarely |
| T1 Architecture | `architecture/` | system patterns, tech context, **ADRs (with machine-readable rules)** | on decisions |
| T2 Map | `map/` | derived repo map: modules, symbols, reference edges | regenerated |
| T3 Active | `active/` | current focus, progress, open questions | every session |
| T4 Memory | `memory/` | journal observations, learnings, handoffs | constantly |

A disposable SQLite index (FTS5 + local vectors + link graph) is derived from these files for instant recall. **Markdown is always the source of truth; delete the index any time.**

`.torsor/` is committed, so it follows `git clone` and is the same memory whichever agent you open — Claude Code, Codex and Cursor each keep their own built-in memory on one machine, in one tool; this one lives in the repo.

## The first hour: set up your project's memory

1. **Scaffold and connect** (see [how-to-install.md](how-to-install.md)):
   ```bash
   torsor init --write && torsor doctor
   ```
2. **Your existing docs are already memory.** `README.md`, `CONTRIBUTING.md`,
   `ARCHITECTURE.md`, `DESIGN.md` and everything under `docs/`, `doc/`, `adr/`
   and `rfcs/` are indexed where they are — `recall` searches them from the
   first query, as the `DOCS` tier. torsor reads them and never writes them;
   nothing is copied into `.torsor/`. Point it at your own layout in
   `.torsor/torsor.toml`:
   ```toml
   [memory]
   sources = ["README.md", "docs/**/*.md", "website/docs/**/*.md", "plans/**/*.md"]
   ```
   Patterns are anchored at the project root (`README.md` is the top-level
   one, not every README) and cannot reach outside it. `CLAUDE.md` and
   `AGENTS.md` are left out on purpose: your client already loads them, so
   recalling them again only spends tokens.
3. **Fill in the two files that matter most** — open `.torsor/charter.md` (what you're building, why, the principles you refuse to break) and `.torsor/architecture/system-patterns.md` (layering, conventions, patterns in use). Two honest paragraphs each beat empty templates. Your agent can draft them: *"read the codebase and fill in .torsor/charter.md and architecture/system-patterns.md"*.
4. **Record your first real decision with a rule** so the guard has teeth — e.g. ask the agent to call:
   ```
   record_decision(
     title="Domain layer must not import the web layer",
     context="...", decision="...",
     rules=[{"kind": "forbid_import", "target": "app.web", "scope": "app/domain/*.py"}]
   )
   ```
5. **Put the rules in the prompt** so every agent sees them for free:
   ```bash
   torsor rules --write AGENTS.md     # or CLAUDE.md — refresh after recording new ADRs
   ```
6. **Map the repo** and **commit `.torsor/`**:
   ```bash
   torsor map && git add .torsor && git commit -m "Add project memory"
   ```

## The daily loop

1. **Session start** — the agent calls `bootstrap_session()`: a token-budgeted summary of charter → architecture → active state → recent memory, plus a short Coach digest. (Tell your agent to do this in your AGENTS.md/CLAUDE.md if it doesn't on its own.)
2. **Before building** — `recall("have we decided how auth works?")` and `get_intent("payments")` surface prior decisions and the symbols that already exist, so the agent extends instead of duplicating.
3. **While working** — the agent records what it learns: `remember("SQLite WAL needed for concurrent CLI+server use", kind="learning")` and keeps `update_active(...)` current.
4. **Before a commit** — `check_drift()` (or `torsor guard`) flags changes that violate ADR rules; `check_dependencies()` (or `torsor deps`) flags imports that resolve to no known package.
5. **Session end** — `handoff(summary=..., next_steps=...)` writes the note the next session resumes from. This is the single highest-value habit.
6. **Weekly-ish** — `torsor coach` for recommendations, `torsor clean` to see what has become dead weight.

Install the hooks once (`torsor hooks install`) and steps 1, 4 and 5 run themselves in Claude Code: the digest is injected at session start, every proposed edit is checked against your ADRs before it lands, and the handoff is written when the session ends.

## Saving tokens: the primer and the command book

```bash
torsor primer --write AGENTS.md       # or CLAUDE.md; --tokens 800 by default
```

Writes a budgeted, managed block — what the project is, how it's architected, the key modules, plus token-efficiency habits (recall before re-reading files, impact instead of repo-grep, bootstrap once). Content the agent reads at prompt time costs **zero discovery tool-calls per session**. Re-run after big changes; it replaces the block, never duplicates. Coexists with the `torsor rules` block in the same file.

```bash
torsor commands --add test 'uv run pytest' --note 'run the suite'
torsor commands --add lint 'uv run ruff check src tests'
torsor commands                       # list; torsor commands --run test replays one
```

The command book lives in committed Markdown (`.torsor/commands.md`) and is shown in the primer, so no session re-derives "how do I run the tests here?". The MCP server records and lists commands but never executes them; only the CLI's `--run` does.

## Keeping your architecture: ADRs → rules → guard

ADRs carry machine-readable `rules:` in their frontmatter. Four rule kinds:

| Kind | Meaning | `target` |
|---|---|---|
| `forbid_import` | files in scope may not import this module | module prefix, e.g. `requests` or `app.web` |
| `forbid_layer_import` | layering: scope X may not import anything matching the regex | regex over dotted module paths, e.g. `features\.b(\.|$)` |
| `require_import` | mandatory seam: files in scope must import this | module prefix, e.g. `app.audit` |
| `forbid_pattern` | line-level regex ban | regex, e.g. `print\(` |

Each rule takes an optional `scope` (fnmatch glob, default `*.py`), `severity` (`hint`/`info`/`warning`/`error`), and `message`.

**Workflow:**

```bash
torsor guard                       # check git-changed files (relative imports are resolved — no bypass)
torsor guard --update-baseline     # adopting on a messy repo: grandfather existing violations
torsor guard --strict --severity error   # CI: fail only on NEW violations at/above the threshold
torsor guard --json                # machine-readable findings
```

CI example (`.github/workflows/guard.yml` step):

```yaml
- run: uv run torsor guard --strict
```

Changed your mind? `record_decision(..., supersedes="0003")` marks the old ADR superseded so stale intent stops surfacing in recall. The guard is **advisory by default** — it informs; it never edits code. With `torsor hooks install` the same rules run as a Claude Code `PreToolUse` hook against each *proposed* Edit/Write, citing the ADR before the change lands; set `automation.guard_on_edit = "block"` in `torsor.toml` to make that a hard stop instead of a warning.

## Understanding the codebase: map → intent → impact

```bash
torsor map                 # symbol map + real "who calls what" reference edges (skips when unchanged)
torsor impact format_date  # blast radius: every caller, AND every decision that mentions it
torsor connect handle_request save_order   # shortest call-graph path between two symbols
```

- `get_intent(topic)` (MCP) combines architecture notes with relevant existing symbols — call it before building a feature.
- Run `torsor impact <symbol>` **before letting an agent rename/regenerate a function** — one regenerated symbol silently breaking far-off callers is a classic agent failure.
- `impact` answers both halves of that question. Alongside the callers it lists the decisions, learnings and handoffs that name the symbol in backticks — so the recorded reason a function looks the way it does arrives *with* the list of what breaks, instead of being rediscovered afterwards. The two are independent: a symbol nothing calls can still be the one the team argued about.
- `torsor recall <query> --symbol <name>` narrows memory to what was written down about one function or class.
- The map covers Python (stdlib `ast`, always on) plus JavaScript/TypeScript/TSX and Go via the optional `[languages]` extra (official tree-sitter grammar wheels, offline — see ADR 0013, which supersedes ADR 0003); without the extra installed it stays Python-only. Ref counts only count *resolved* references, never comments or strings.

## Dependency safety

```bash
torsor deps                # offline check of git-changed files
torsor deps --strict       # CI: fail on any unknown import
```

Flags imports that resolve to neither stdlib, installed packages, declared dependencies, nor first-party code — the **slopsquatting** failure mode where an agent imports a package that doesn't exist. Fully offline; checks the top-level name only, so verify unfamiliar suggestions independently.

## The Coach + housekeeping

```bash
torsor coach                       # health (thin/stale/uncharted) · hotspots · phantom deps · dangling links
torsor coach --dismiss <key>       # silence a recommendation for good
torsor stale                       # memory that points at code that no longer exists
torsor clean                       # dry-run GC of derived artefacts; --apply to reclaim
torsor index [--full]              # rebuild the derived index explicitly (recall does this incrementally anyway)
```

Every recommendation comes with evidence and a concrete action, ranked by severity, and decays so it never nags. A 3-item digest is also pushed into `bootstrap_session()` output (silent when healthy).

The Coach also tracks what you **fixed**. When a recommendation stops being produced, the next `torsor coach` says so once (`Fixed since last time: …`) and forgets it. An `important` recommendation you have left alone for a week starts carrying its age (`open 14 days`) — as information, not as a higher rank, because the decay that keeps the Coach quiet is deliberate.

## CLI reference

| Command | What it does |
|---|---|
| `torsor init [--write] [--client <name>] [--force]` | Scaffold `.torsor/`; `--write` emits `.mcp.json`; `--client` prints that client's config + location |
| `torsor --version` | Print the installed version |
| `torsor mcp` | Run the MCP server over stdio |
| `torsor doctor` | Verify the project is healthy |
| `torsor index [--full]` | Build/refresh the derived search index |
| `torsor map [--force]` | Generate the symbol map + reference edges |
| `torsor impact <symbol>` | Who references a symbol across files, and which decisions and learnings mention it |
| `torsor rules [--write <file>] [--client <name>] [--scoped]` | Compact rules digest; `--write`/`--client` maintains a managed block in the agent's instructions file; `--scoped` writes one path-scoped Claude Code rule file per ADR |
| `torsor primer [--write <file>] [--client <name>] [--tokens N]` | Token-saving prompt-time project primer (managed block) |
| `torsor commands [--add NAME COMMAND] [--note ...] [--run name]` | Record & replay project commands (test/build/lint) |
| `torsor guard [files…] [--strict] [--severity <lvl>] [--json] [--update-baseline]` | ADR-rule drift check with CI ratchet |
| `torsor deps [files…] [--strict]` | Offline hallucinated-dependency check |
| `torsor coach [--dismiss <key>] [--limit N]` | Recommendations |
| `torsor stats [--json]` | Notes per tier, map size, index size, what gets recalled most, which embedder is really in use |
| `torsor verify [files…] [--strict] [--severity <lvl>] [--run-tests] [--json]` | One pass/fail gate: guard + deps + staleness, optionally your recorded `test` command. Exits non-zero — use it as a CI or loop completion check |
| `torsor stale [--mark\|--unmark] [--strict] [--json]` | Memory that contradicts the code: dangling `[[wikilinks]]` and dead file paths |
| `torsor clean [--apply] [--deep] [--yes]` | Reclaim orphaned map notes, dead index rows and — only if `clean.journal_retention_days` is set — expired journals. Dry run by default |
| `torsor connect <from> <to> [--max-hops N]` | Shortest call-graph path between two symbols — "how does X reach Y?" |
| `torsor hooks install [--local] [--on-stop] [--no-git] [--no-claude]` | Wire auto-capture into git and Claude Code |
| `torsor hooks uninstall` | Remove only torsor's entries, from both settings files |
| `torsor hooks status` | Which git hooks and Claude Code events carry a torsor entry |
| `torsor hooks run <event>` | What an installed hook calls; you rarely type this |

Upgrading the CLI itself: `uv tool upgrade torsor-helper` (or `pipx upgrade torsor-helper`).

### Memory, from the shell

The same operations the MCP server exposes, for scripting, CI, or debugging
recall without an agent attached.

| Command | What it does |
|---|---|
| `torsor recall <query> [--limit N] [--type T] [--kind K] [--symbol S] [--include-superseded] [--json]` | Hybrid search across memory, wiki and map; `--symbol` keeps only notes that mention that code symbol |
| `torsor remember <text> [--kind K] [--link slug]` | Persist an observation, decision or learning |
| `torsor active --focus … [--progress …] [--open-questions …]` | Update the current working state |
| `torsor handoff <summary> [--decisions …] [--next-steps …]` | End-of-session handoff the next session resumes from |
| `torsor bootstrap [--max-tokens N]` | Print the whole-pyramid digest an agent reads at session start |
| `torsor intent [topic]` | Architecture, decisions and relevant symbols for a topic |
| `torsor decision <title> --context … --decision … [--supersedes …]` | Record an ADR |

## MCP tool reference

| Tool | When the agent should call it |
|---|---|
| `bootstrap_session()` | First thing, every session |
| `get_rules()` | Once per session if rules aren't already in the prompt file |
| `recall(query, limit?)` | Before assuming; "have we decided X?" |
| `remember(content, kind?, links?)` | After a decision, gotcha, or finished chunk |
| `update_active(focus, progress, open_questions)` | When the working focus shifts |
| `handoff(summary, decisions?, open_questions?, next_steps?)` | End of session |
| `get_intent(topic?)` | Before building a feature |
| `map_repo(force?)` / `impact(symbol)` | After big changes / before touching a shared symbol |
| `record_decision(title, context, decision, consequences?, rules?, supersedes?)` | On load-bearing choices |
| `get_primer(max_tokens?)` | Orientation without exploration, if the primer isn't already in the prompt file |
| `check_drift(files?, as_json?, new_only?)` | Before commits |
| `check_dependencies(files?)` | After adding imports |
| `recommend()` | Periodically — the Coach's ranked recommendations |
| `verify(files?, severity?)` | As a completion check — one JSON verdict over guard + deps + staleness |
| `stale(mark?, unmark?)` | When memory may have drifted from the code |
| `connect(source, target, max_hops?)` | "How does X reach Y?" before a refactor |
| `stats()` | How big the memory is, what is recalled, whether the map is current |
| `clean(apply?, deep?)` | Housekeeping; dry run unless `apply` |
| `record_command(name, command, note?)` / `list_commands()` | So no session re-derives how to test or build |
| `dismiss_recommendation(key)` | Stop showing a Coach recommendation |
| `hooks_status()` | Which auto-capture hooks are installed (read-only; installing is CLI-only) |

### Prompts

MCP clients render these as slash-commands, so the loop does not depend on the
agent remembering which tool to call in which order.

| Prompt | What it does |
|---|---|
| `onboard` | Read the project's memory and the standing rules before touching anything |
| `checkpoint` | Close out a session: active state, handoff, anything durable |
| `review_drift` | Run the verification gate and act on what fails |
| `coach` | Get the health recommendations and do the highest-value one |

## FAQ

- **Do I need an API key or internet?** No. Everything works offline; the `embeddings` extra downloads a small local model once.
- **The index broke / looks stale.** `torsor clean --apply --deep --yes`, then `torsor index`. The index is derived and disposable, always.
- **Can I edit the Markdown by hand?** Yes — that's the point. Obsidian works too (`[[wikilinks]]` are first-class). Malformed frontmatter degrades gracefully; it never breaks recall.
- **How do I stop one noisy recommendation?** `torsor coach --dismiss <key>` (the key is printed with each recommendation).
- **What goes in git?** `.torsor/` yes, `.torsor/.index/` and `.torsor/state/` no (the scaffolded `.gitignore` handles it).
- **Two branches both wrote memory and git conflicted.** Journal entries are append-only Markdown — keep both sides. Map notes are derived: take either, then `torsor map --force` regenerates them from source.
- **Does it work with my tool?** `torsor init --client` knows Claude Code, Cursor, Codex, VS Code and Gemini CLI; `--client other` prints the standard `mcpServers` JSON block that every other MCP client accepts.
