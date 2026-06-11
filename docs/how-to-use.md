# How to use torsor-helper

This is the practical, day-to-day guide. For setup, see [how-to-install.md](how-to-install.md); for the design rationale, see the [README](../README.md).

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
torsor impact format_date  # blast radius: every resolved caller of a symbol, across files
torsor export              # portable llms.txt + Mermaid module-dependency diagram
```

- `get_intent(topic)` (MCP) combines architecture notes with relevant existing symbols — call it before building a feature.
- Run `torsor impact <symbol>` **before letting an agent rename/regenerate a function** — one regenerated symbol silently breaking far-off callers is a classic agent failure.
- The map is Python-only today (stdlib `ast`, by design — see ADR 0003); ref counts only count *resolved* references, never comments or strings.

## Dependency safety

```bash
torsor deps                # offline check of git-changed files
torsor deps --strict       # CI: fail on any unknown import
```

Flags imports that resolve to neither stdlib, installed packages, declared dependencies, nor first-party code — the **slopsquatting** failure mode where an agent imports a package that doesn't exist. Fully offline; checks the top-level name only, so verify unfamiliar suggestions independently.

## The Coach + housekeeping

```bash
torsor coach                       # health · reuse · hotspots · temporal coupling · regressions · phantom deps
torsor coach --dismiss <key>       # silence a recommendation for good
torsor consolidate                 # mine journal → per-topic insight notes; reindex; snapshot complexity
torsor index [--full]              # rebuild the derived index explicitly (recall does this incrementally anyway)
```

Every recommendation comes with evidence and a concrete action, ranked by severity, and decays so it never nags. A 3-item digest is also pushed into `bootstrap_session()` output (silent when healthy).

## CLI reference

| Command | What it does |
|---|---|
| `torsor init [--write] [--client <name>] [--force]` | Scaffold `.torsor/`; `--write` emits `.mcp.json`; `--client` prints that client's config + location |
| `torsor --version` | Print the installed version |
| `torsor mcp [--http --host --port]` | Run the MCP server (stdio default; `--http` for a shared service) |
| `torsor doctor` | Verify the project is healthy |
| `torsor index [--full]` | Build/refresh the derived search index |
| `torsor map [--force]` | Generate the symbol map + reference edges |
| `torsor impact <symbol>` | Who references a symbol, across files |
| `torsor export` | `llms.txt` + Mermaid module diagram |
| `torsor rules [--write <file>]` | Compact rules digest; `--write` maintains a managed block in AGENTS.md/CLAUDE.md |
| `torsor guard [files…] [--strict] [--severity <lvl>] [--json] [--update-baseline]` | ADR-rule drift check with CI ratchet |
| `torsor deps [files…] [--strict]` | Offline hallucinated-dependency check |
| `torsor coach [context] [--dismiss <key>]` | Recommendations |
| `torsor consolidate` | Journal → insights maintenance pass |

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
| `check_drift(files?, as_json?, new_only?)` | Before commits |
| `check_dependencies(files?)` | After adding imports |
| `export()` / `recommend(context?)` / `consolidate()` | Periodically |

## Team / HTTP mode

```bash
torsor mcp --http --port 8000              # serves http://127.0.0.1:8000/mcp
```

stdio is the default and right for a single local agent. **The HTTP transport has no authentication** — binding a non-loopback host (`--host 0.0.0.0`) prints a loud warning because it exposes read/write project memory to anyone who can reach the port. For team use, keep it behind a reverse proxy with auth or an SSH tunnel. Sharing memory via git (commit `.torsor/`) is the simplest team setup.

## FAQ

- **Do I need an API key or internet?** No. Everything works offline; the `embeddings` extra downloads a small local model once.
- **The index broke / looks stale.** Delete `.torsor/.index/` and run `torsor index`. The index is derived and disposable, always.
- **Can I edit the Markdown by hand?** Yes — that's the point. Obsidian works too (`[[wikilinks]]` are first-class). Malformed frontmatter degrades gracefully; it never breaks recall.
- **How do I stop one noisy recommendation?** `torsor coach --dismiss <key>` (the key is printed with each recommendation).
- **What goes in git?** `.torsor/` yes, `.torsor/.index/` no (scaffolded `.gitignore` handles it).
