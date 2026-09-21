# How to use torsor-helper

This is the practical, day-to-day reference. New to vibe-coding with torsor? Start with the [**Vibe-coding guide**](vibe-coding-guide.md). For setup, see [how-to-install.md](how-to-install.md); for the design rationale, see the [README](../README.md).

**Contents:** [Mental model](#the-mental-model-60-seconds) · [First hour](#the-first-hour-set-up-your-projects-memory) · [Daily loop](#the-daily-loop) · [Architecture rules](#keeping-your-architecture-adrs--rules--guard) · [Codebase map](#understanding-the-codebase-map--intent--impact) · [Dependency safety](#dependency-safety) · [The Coach](#the-coach--housekeeping) · [CLI reference](#cli-reference) · [MCP tool reference](#mcp-tool-reference) · [Team / HTTP mode](#team--http-mode) · [FAQ](#faq)

## The mental model (60 seconds)

Your project's memory is **plain Markdown you own**, under `.torsor/`, in five tiers ordered by stability:

| Tier | Folder | Holds | Changes |
|---|---|---|---|
| T0 Charter | `charter.md` | what & why, non-negotiable principles | rarely |
| T1 Architecture | `architecture/` | system patterns, tech context, **ADRs (with machine-readable rules)** | on decisions |
| T2 Map | `map/` | derived repo map: modules, symbols, reference edges | regenerated |
| T3 Active | `active/` | current focus, progress, open questions | every session |
| T4 Memory | `memory/` | journal observations, learnings, handoffs, mined insights | constantly |

A disposable SQLite index (FTS5 + local vectors + link graph) is derived from these files for instant recall. **Markdown is always the source of truth; delete the index any time.**

## The first hour: set up your project's memory

1. **Scaffold and connect** (see [how-to-install.md](how-to-install.md)):
   ```bash
   torsor init --write && torsor doctor
   ```
2. **Fill in the two files that matter most** — open `.torsor/charter.md` (what you're building, why, the principles you refuse to break) and `.torsor/architecture/system-patterns.md` (layering, conventions, patterns in use). Two honest paragraphs each beat empty templates. Your agent can draft them: *"read the codebase and fill in .torsor/charter.md and architecture/system-patterns.md"*.
3. **Record your first real decision with a rule** so the guard has teeth — e.g. ask the agent to call:
   ```
   record_decision(
     title="Domain layer must not import the web layer",
     context="...", decision="...",
     rules=[{"kind": "forbid_import", "target": "app.web", "scope": "app/domain/*.py"}]
   )
   ```
4. **Put the rules in the prompt** so every agent sees them for free:
   ```bash
   torsor rules --write AGENTS.md     # or CLAUDE.md — refresh after recording new ADRs
   ```
5. **Map the repo** and **commit `.torsor/`**:
   ```bash
   torsor map && git add .torsor && git commit -m "Add project memory"
   ```

## The daily loop

1. **Session start** — the agent calls `bootstrap_session()`: a token-budgeted summary of charter → architecture → active state → recent memory, plus a short Coach digest. (Tell your agent to do this in your AGENTS.md/CLAUDE.md if it doesn't on its own.)
2. **Before building** — `recall("have we decided how auth works?")` and `get_intent("payments")` surface prior decisions and the symbols that already exist, so the agent extends instead of duplicating.
3. **While working** — the agent records what it learns: `remember("SQLite WAL needed for concurrent CLI+server use", kind="learning")` and keeps `update_active(...)` current.
4. **Before a commit** — `check_drift()` (or `torsor guard`) flags changes that violate ADR rules; `check_dependencies()` (or `torsor deps`) flags imports that resolve to no known package.
5. **Session end** — `handoff(summary=..., next_steps=...)` writes the note the next session resumes from. This is the single highest-value habit.
6. **Weekly-ish** — `torsor coach` for recommendations, `torsor consolidate` to distill the journal into per-topic insight notes.

## Instant guardrails: best-practice packs

Don't want to write rules from scratch? Adopt a curated pack — the consensus of major style guides and default linter rules (PEP 8/ruff/bandit, ESLint/typescript-eslint recommended, Uber Go guide, clippy), weighted toward mistakes AI agents are *documented* to make (swallowed exceptions, XSS sinks, `as any`, leftover debug output, hardcoded secrets, `todo!()` stubs):

```bash
torsor practices                      # auto-detect languages, list the packs
torsor practices python --apply       # record the pack as an ADR (guard now enforces its rules)
torsor guard --update-baseline        # grandfather pre-existing violations once
torsor rules --write AGENTS.md        # put the principles in the prompt
```

Packs: `python` · `javascript` · `typescript` (includes the JS pack) · `go` · `rust` · `agent` (language-agnostic AI-hygiene: secrets, commented-out code, untagged TODOs, …). Each pack is one ADR — edit or supersede it like any other decision. Severity policy: only near-zero-false-positive patterns are `error`; noisier ones ship as `warning`/`hint` so `--strict --severity error` stays trustworthy.

## Saving tokens: the primer

```bash
torsor primer --write AGENTS.md       # or CLAUDE.md; --tokens 800 by default
```

Writes a budgeted, managed block — what the project is, how it's architected, the key modules, plus token-efficiency habits (recall before re-reading files, impact instead of repo-grep, bootstrap once). Content the agent reads at prompt time costs **zero discovery tool-calls per session**. Re-run after big changes; it replaces the block, never duplicates. Coexists with the `torsor rules` block in the same file.

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

Changed your mind? `record_decision(..., supersedes="0003")` marks the old ADR superseded so stale intent stops surfacing in recall. The guard is **advisory by design** — it informs; it never blocks or edits code.

## Understanding the codebase: map → intent → impact

```bash
torsor map                 # symbol map + real "who calls what" reference edges (skips when unchanged)
torsor impact format_date  # blast radius: every caller, AND every decision that mentions it
torsor export              # portable llms.txt + Mermaid module-dependency diagram
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
torsor coach                       # health · reuse · hotspots · coupling · regressions · phantom deps · contradictions
torsor coach --dismiss <key>       # silence a recommendation for good
torsor consolidate                 # mine journal → per-topic insight notes; reindex; snapshot complexity
torsor index [--full]              # rebuild the derived index explicitly (recall does this incrementally anyway)
```

Every recommendation comes with evidence and a concrete action, ranked by severity, and decays so it never nags. A 3-item digest is also pushed into `bootstrap_session()` output (silent when healthy).

The Coach also tracks what you **fixed**. When a recommendation stops being produced, the next `torsor coach` says so once (`Fixed since last time: …`) and forgets it. An `important` recommendation you have left alone for a week starts carrying its age (`open 14 days`) — as information, not as a higher rank, because the decay that keeps the Coach quiet is deliberate.

One check reads memory rather than code: **contradictions**. Two active `type: decision` notes whose titles are about the same thing and state opposite decisions get flagged, because that is how an ADR set rots — a decision gets reversed in a new ADR and the old one is never marked `status: superseded`, so the guard enforces one rule while the agent reads the other. It is deliberately conservative and will miss more than it catches: detection is term overlap plus polarity, never embeddings, since the default embedder is a hashing fallback that finds similarity between any two texts at all. An explicit `supersedes:` link or `status: superseded` exempts a pair — that is the correct workflow, not a contradiction.

## CLI reference

| Command | What it does |
|---|---|
| `torsor init [--write] [--client <name>] [--force]` | Scaffold `.torsor/`; `--write` emits `.mcp.json`; `--client` prints that client's config + location |
| `torsor --version` | Print the installed version |
| `torsor mcp [--http --host --port]` | Run the MCP server (stdio default; `--http` for a shared service) |
| `torsor doctor` | Verify the project is healthy |
| `torsor index [--full]` | Build/refresh the derived search index |
| `torsor map [--force]` | Generate the symbol map + reference edges |
| `torsor impact <symbol>` | Who references a symbol across files, and which decisions and learnings mention it |
| `torsor export` | `llms.txt` + Mermaid module diagram |
| `torsor rules [--write <file>] [--client <name>]` | Compact rules digest; `--write`/`--client` maintains a managed block in the agent's instructions file |
| `torsor practices [<lang>] [--apply]` | List/adopt curated best-practice packs as guard-enforced ADRs |
| `torsor primer [--write <file>] [--client <name>] [--tokens N]` | Token-saving prompt-time project primer (managed block) |
| `torsor commands [--add NAME COMMAND] [--note ...] [--run name]` | Record & replay project commands (test/build/lint) |
| `torsor recipes [--limit N]` | Most-repeated deterministic lookups — candidates for the cheap model |
| `torsor models [--cheap … --smart …] [--write <file>\|--client <name>] [--json]` | Cheap/smart model-routing policy (Markdown block, JSON, or MCP) |
| `torsor find <query> [--mode] [--files-only\|--symbols-only]` | Fuzzy + frecency search over files and mapped symbols |
| `torsor update [--print-only]` | Self-update the CLI (detects uv tool / pipx / pip) |
| `torsor guard [files…] [--strict] [--severity <lvl>] [--json] [--update-baseline]` | ADR-rule drift check with CI ratchet |
| `torsor deps [files…] [--strict]` | Offline hallucinated-dependency check |
| `torsor coach [context] [--dismiss <key>] [--limit N]` | Recommendations |
| `torsor consolidate` | Journal → insights maintenance pass |
| `torsor stats [--json]` | Notes per tier, map size, index size, what gets recalled most, which embedder is really in use |
| `torsor verify [files…] [--strict] [--severity <lvl>] [--run-tests] [--json]` | One pass/fail gate: guard + deps + staleness, optionally your recorded `test` command. Exits non-zero — use it as a CI or loop completion check |
| `torsor stale [--mark\|--unmark] [--strict] [--json]` | Memory that contradicts the code: dangling `[[wikilinks]]` and dead file paths |
| `torsor clean [--apply] [--deep] [--yes]` | Reclaim orphaned map notes, dead index rows and expired journals. Dry run by default |
| `torsor connect <from> <to> [--max-hops N]` | Shortest call-graph path between two symbols — "how does X reach Y?" |
| `torsor hooks install [--local] [--on-stop] [--no-git] [--no-claude]` | Wire auto-capture into git and Claude Code |
| `torsor hooks uninstall` | Remove only torsor's entries, from both settings files |
| `torsor hooks status` | Which git hooks and Claude Code events carry a torsor entry |
| `torsor hooks run <event>` | What an installed hook calls; you rarely type this |
| `torsor merge install` | Set `.torsor/` up for concurrent branches: writes `.gitattributes` (commit it) and registers the map merge driver in this clone |
| `torsor merge status [--json]` | Whether both halves are in place here — the committed one and the one only your clone can have |

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
| `get_primer(max_tokens?)` / `list_practices(lang?)` / `adopt_practices(lang)` | Orientation without exploration; instant guardrail packs |
| `check_drift(files?, as_json?, new_only?)` | Before commits |
| `check_dependencies(files?)` | After adding imports |
| `export()` / `recommend(context?)` / `consolidate()` | Periodically |
| `verify(files?, severity?)` | As a completion check — one JSON verdict over guard + deps + staleness |
| `stale(mark?, unmark?)` | When memory may have drifted from the code |
| `connect(source, target, max_hops?)` | "How does X reach Y?" before a refactor |
| `find_files(query, mode?, limit?, include_files?, include_symbols?)` | Navigation: jump to a file or symbol without exploring |
| `stats()` | How big the memory is, what is recalled, whether the map is current |
| `clean(apply?, deep?)` | Housekeeping; dry run unless `apply` |
| `record_command(name, command, note?)` / `list_commands()` | So no session re-derives how to test or build |
| `recipes(limit?)` / `get_model_policy(as_json?)` | Which lookups recur, and which model tier to route them to |
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

## Team / HTTP mode

```bash
torsor mcp --http --port 8000              # serves http://127.0.0.1:8000/mcp
```

stdio is the default and right for a single local agent. **The HTTP transport has no authentication** — binding a non-loopback host (`--host 0.0.0.0`) is refused unless you also pass `--allow-remote`, because it exposes read/write project memory to anyone who can reach the port. For team use, keep it behind a reverse proxy with auth or an SSH tunnel.

### Sharing memory through git

Committing `.torsor/` is the simplest team setup, and the thing that makes it
sustainable is that concurrent branches stop conflicting:

```bash
torsor merge install    # once per clone — and it means once per person
git add .torsor/.gitattributes && git commit -m "torsor: merge rules"
```

Two halves, because git only lets you distribute one of them:

- **`.torsor/.gitattributes` is committed**, so every clone gets it. It gives
  `memory/journal/*.md` a `union` merge, which keeps both sides' entries. This
  half needs no setup at all — it is the common conflict, and it is solved for
  everyone the moment the file is committed.
- **The `map/**` driver lives in `.git/config`**, which cannot be committed, so
  each person runs `torsor merge install` once. Map notes are derived, so the
  driver keeps yours and queues the note for regeneration; the next
  `torsor map --force` (or the post-commit hook) rebuilds it from source.

Git does **not** warn when the attributes file names a driver your clone has
not registered — it quietly falls back to the ordinary text merge, which looks
identical to having configured nothing. `torsor merge status` and `torsor
doctor` both say so explicitly, which is the only way to find out.

On a larger team, `memory.journal_partition = "date-author"` in `torsor.toml`
gives each git identity its own journal file, so concurrent work never touches
the same path in the first place.

## FAQ

- **Do I need an API key or internet?** No. Everything works offline; the `embeddings` extra downloads a small local model once.
- **The index broke / looks stale.** `torsor clean --apply --deep --yes`, then `torsor index`. The index is derived and disposable, always.
- **Can I edit the Markdown by hand?** Yes — that's the point. Obsidian works too (`[[wikilinks]]` are first-class). Malformed frontmatter degrades gracefully; it never breaks recall.
- **How do I stop one noisy recommendation?** `torsor coach --dismiss <key>` (the key is printed with each recommendation).
- **What goes in git?** `.torsor/` yes, `.torsor/.index/` and `.torsor/state/` no (the scaffolded `.gitignore` handles it). `.torsor/.gitattributes` **is** committed — it is how a clone learns the merge rules.
- **Two branches both wrote memory and git conflicted.** Run `torsor merge install` (see Team mode). Journals then union-merge and map notes regenerate.
