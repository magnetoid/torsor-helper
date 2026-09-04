from __future__ import annotations

import re as _re
from collections import deque

from torsor_helper import cartographer, cleaner, db, export as _export, guard
from torsor_helper.coach import mining as coach_mining
from torsor_helper.coach import report as coach_report
from torsor_helper.coach.state import CoachState
from torsor_helper.budget import estimate_tokens, truncate_to_tokens
from torsor_helper.config import TorsorConfig
from torsor_helper.embeddings import get_embedder
from torsor_helper.indexer import reindex
from torsor_helper.models import Frontmatter, RecallResult
from torsor_helper.recall import keyword_recall
from torsor_helper.search import hybrid_search
from torsor_helper.store import Store

# Fractions of the bootstrap budget allocated per section (must sum to <= 1.0).
_BOOTSTRAP_ALLOC = [
    ("Charter", "charter", 0.30),
    ("System Patterns", "system_patterns", 0.20),
    ("Tech Context", "tech_context", 0.15),
    ("Active Context", "active_context", 0.18),
    ("Progress", "progress", 0.10),
]
_RECENT_JOURNAL_FRACTION = 0.07


def bootstrap_session(store: Store, config: TorsorConfig, *, max_tokens: int | None = None) -> str:
    cpt = config.budgets.chars_per_token
    total = max_tokens or config.budgets.bootstrap_tokens
    sections: list[str] = []

    for label, attr, frac in _BOOTSTRAP_ALLOC:
        path = getattr(store.paths, attr)
        if not path.exists():
            continue
        note = store.read_note(path)
        text = truncate_to_tokens(note.body.strip(), int(total * frac), cpt)
        if text.strip():
            sections.append(f"## {label}\n\n{text}")

    recent = _recent_journal(store, int(total * _RECENT_JOURNAL_FRACTION), cpt)
    if recent:
        sections.append(f"## Recent Memory\n\n{recent}")

    # Push a short hygiene digest from the Coach (index-free, dismissible).
    digest = coach_report.session_digest(store, limit=3)
    if digest:
        lines = "\n".join(f"- [{rec.severity}] {rec.message}" for rec in digest)
        sections.append(f"## Recommendations\n\n{lines}")

    return "\n\n".join(sections)


_SESSION_START_HEADER = (
    "torsor: project memory, {when}. Do NOT call bootstrap_session() — this is it; "
    "reach for recall() / get_intent() / impact() when you need more than this digest.\n\n"
)


def session_start_context(store: Store, config: TorsorConfig, *, how: str = "startup") -> str | None:
    """The digest the Claude Code SessionStart hook injects. Same composition as
    bootstrap_session, under the smaller session_start budget, prefixed with a
    line that stops the agent from spending a tool call re-fetching it. None
    when disabled (config.automation.auto_bootstrap) or when there is nothing
    to say — the adapter then emits nothing, and the session starts untouched."""
    if not config.automation.auto_bootstrap:
        return None
    body = bootstrap_session(store, config, max_tokens=config.budgets.session_start_tokens)
    if not body.strip():
        return None
    when = "re-injected after context compaction" if how == "compact" else "injected at session start"
    return _SESSION_START_HEADER.format(when=when) + body


def _recent_journal(store: Store, max_tokens: int, cpt: int) -> str:
    if not store.paths.journal_dir.exists():
        return ""
    # Newest day first, so a fresh/sparse latest day still surfaces prior memory.
    journals = sorted(store.paths.journal_dir.glob("*.md"), reverse=True)
    parts: list[str] = []
    used = 0
    for jpath in journals:
        body = store.read_note(jpath).body.strip()
        if not body:
            continue
        cost = estimate_tokens(body, cpt)
        if parts and used + cost > max_tokens:
            break
        parts.append(body)
        used += cost
    return truncate_to_tokens("\n\n".join(parts), max_tokens, cpt)


_EMBEDDER_CACHE: dict = {}


def _embedder_for(config):
    key = (config.embeddings.provider, config.embeddings.model, config.embeddings.dim)
    if key not in _EMBEDDER_CACHE:
        _EMBEDDER_CACHE[key] = get_embedder(config)
    return _EMBEDDER_CACHE[key]


def _open_index(store, config):
    """Return a freshly-synced index connection, or None to use keyword fallback."""
    if not config.index.auto_index and not store.paths.index_db.exists():
        return None
    embedder = _embedder_for(config)
    conn = db.connect(store.paths.index_db)
    try:
        reindex(store, conn, embedder)
    except Exception:
        conn.close()  # don't leak the connection if indexing fails
        raise
    return conn


def recall(store: Store, config: TorsorConfig, query: str, limit: int = 8) -> RecallResult:
    _log_op(store, "recall", query)
    conn = _open_index(store, config)
    if conn is not None:
        try:
            return hybrid_search(
                conn, _embedder_for(config), config, query,
                limit=limit, max_tokens=config.budgets.recall_tokens,
            )
        finally:
            conn.close()
    notes = list(store.iter_notes())
    return keyword_recall(
        notes, query, limit=limit,
        chars_per_token=config.budgets.chars_per_token,
        max_tokens=config.budgets.recall_tokens,
    )


def remember(store: Store, content: str, kind: str = "observation", links: list[str] | None = None) -> str:
    path = store.append_journal(content, kind=kind, links=links or [])
    return str(path)


def update_active(store: Store, focus: str, progress: str, open_questions: str) -> None:
    store.write_note(
        store.paths.active_context,
        Frontmatter(type="active-context", tags=["active"]),
        "Active Context",
        f"## Current focus\n{focus}\n\n## Open questions\n{open_questions}\n",
    )
    store.write_note(
        store.paths.progress,
        Frontmatter(type="progress", tags=["active"]),
        "Progress",
        f"{progress}\n",
    )


def record_handoff(
    store: Store,
    summary: str,
    decisions: str = "",
    open_questions: str = "",
    next_steps: str = "",
) -> str:
    body = (
        f"**Summary:** {summary}\n\n"
        f"**Decisions:** {decisions or '—'}\n\n"
        f"**Open questions:** {open_questions or '—'}\n\n"
        f"**Next steps:** {next_steps or '—'}"
    )
    path = store.append_journal(body, kind="handoff", links=[])
    return str(path)


def map_repo(store: Store, config: TorsorConfig, paths: list[str] | None = None, force: bool = False) -> dict:
    full_scan = paths is None
    fingerprint = cartographer.repo_fingerprint(store.paths.root) if full_scan else None

    conn = db.connect(store.paths.index_db)
    try:
        # Skip the whole scan+render+reindex when the repo is byte-for-byte
        # unchanged since the last full map (a partial `paths` map never skips).
        if full_scan and not force and fingerprint == db.meta_get(conn, "map_fingerprint"):
            return {
                "skipped": True,
                "modules": len(db.modules(conn)),
                "symbols": conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0],
                "edges": conn.execute("SELECT COUNT(*) FROM symbol_edges").fetchone()[0],
            }

        symbols, edges = cartographer.scan_repo_with_edges(store.paths.root, paths)
        if not full_scan:
            # Merge the rescanned modules into the existing graph rather than
            # replacing it wholesale, then recompute refs across the union so
            # cross-module counts to/from unscanned modules stay correct. The
            # result is identical to a pristine full remap. (Truly incremental,
            # skip-unchanged mapping is I-20 / the tree-sitter fast-follow.)
            scanned = cartographer.scanned_modules(store.paths.root, paths)
            symbols = [s for s in db.load_symbols(conn) if s.module not in scanned] + symbols
            edges = [e for e in db.load_edges(conn) if e.module not in scanned] + edges
            cartographer.compute_refs(symbols, edges)

        rendered = cartographer.render_map(
            symbols,
            overview_tokens=config.budgets.bootstrap_tokens,
            chars_per_token=config.budgets.chars_per_token,
        )
        for relpath, (title, body) in rendered.items():
            target = store.paths.map_dir / relpath
            store.write_note(target, Frontmatter(type="map", status="derived", tags=["map"]), title, body)

        db.replace_all_symbols(conn, symbols)
        db.replace_all_edges(conn, edges)
        reindex(store, conn, _embedder_for(config))
        if full_scan:
            db.meta_set(conn, "map_fingerprint", fingerprint)
        else:
            # The stored fingerprint reflects the last full scan; a partial map
            # doesn't re-verify the whole tree, so clear it to force the next
            # full map to actually run rather than falsely skip.
            db.meta_set(conn, "map_fingerprint", "")
        conn.commit()
    finally:
        conn.close()

    return {
        "skipped": False,
        "modules": len({s.module for s in symbols}),
        "symbols": len(symbols),
        "edges": len(edges),
    }


def export_project(store: Store, config: TorsorConfig) -> dict:
    return _export.export_project(store, config)


def find_targets(store: Store, config: TorsorConfig, query: str, *, mode: str = "fuzzy",
                 limit: int = 20, include_files: bool = True, include_symbols: bool = True) -> list:
    """Fuzzy/literal/regex find over repo files + mapped symbols, frecency-ranked."""
    _log_op(store, "find_files", query)
    from torsor_helper import finder

    return finder.find(store, config, query, mode=mode, limit=limit,
                       include_files=include_files, include_symbols=include_symbols)


_RULES_START = "<!-- torsor:rules -->"
_RULES_END = "<!-- /torsor:rules -->"


def _charter_section(body: str, heading: str) -> str:
    """Lines under `## <heading>` up to the next H2 (empty string if absent)."""
    match = _re.search(rf"^##\s+{_re.escape(heading)}\s*$\n(.*?)(?=^##\s|\Z)", body, _re.MULTILINE | _re.DOTALL)
    return match.group(1).strip() if match else ""


def agent_rules(store: Store, config: TorsorConfig, *, max_tokens: int = 600) -> str:
    """A compact, token-budgeted digest of the project's standing constraints —
    charter principles + machine-readable ADR rules — for agent prompt files
    (AGENTS.md / CLAUDE.md). Rules the agent sees at prompt time cost zero
    tool-call tokens per session, and the guard still enforces them in CI."""
    _log_op(store, "get_rules", "")
    sections: list[str] = []

    if store.paths.charter.exists():
        principles = _charter_section(store.read_note(store.paths.charter).body, "Non-negotiable principles")
        if principles:
            sections.append(f"### Non-negotiable principles\n{principles}")

    rules = guard.load_rules(store)
    if rules:
        lines = []
        for r in rules:
            scope = f" in `{r.scope}`" if r.scope and r.scope != "*.py" else ""
            message = f" — {r.message}" if r.message else ""
            lines.append(f"- {r.kind}: `{r.target}`{scope}{message} (per {r.source})")
        sections.append(
            "### Architecture rules (machine-enforced — `torsor guard` flags violations)\n" + "\n".join(lines)
        )

    if not sections:
        return ""
    digest = "## Project rules (torsor-helper)\n\n" + "\n\n".join(sections)
    return truncate_to_tokens(digest, max_tokens, config.budgets.chars_per_token)


def _write_managed_block(target, start: str, end: str, content: str) -> str:
    """Write/refresh a marker-delimited block in `target` (AGENTS.md,
    CLAUDE.md, …). Idempotent — re-running replaces the block, never duplicates."""
    from pathlib import Path

    block = f"{start}\n{content}\n{end}"
    target = Path(target)
    if target.exists():
        text = target.read_text(encoding="utf-8")
        if start in text and end in text:
            pre, rest = text.split(start, 1)
            post = rest.split(end, 1)[1]
            new = pre + block + post
        else:
            new = text.rstrip() + "\n\n" + block + "\n"
    else:
        new = block + "\n"
    target.write_text(new, encoding="utf-8")
    return str(target)


def write_rules_block(store: Store, config: TorsorConfig, target) -> str:
    return _write_managed_block(target, _RULES_START, _RULES_END, agent_rules(store, config))


def _rule_line(r) -> str:
    scope = f" in `{r.scope}`" if r.scope and r.scope != "*.py" else ""
    message = f" — {r.message}" if r.message else ""
    return f"- {r.kind}: `{r.target}`{scope}{message}"


def _scope_to_paths_glob(scope: str) -> str:
    """A guard rule's fnmatch scope → a Claude Code `paths:` glob (matched
    relative to the project root). fnmatch's `*.py` means "any .py, anywhere",
    which in glob terms is `**/*.py`; a scope that already names a directory is
    passed through unchanged."""
    scope = scope or "*.py"
    return scope if "/" in scope else f"**/{scope}"


# HTML comments are stripped from a rule file before it enters context, so this
# provenance line costs zero tokens (Claude Code memory docs).
_SCOPED_PROVENANCE = "<!-- generated by `torsor rules --scoped` from {src}; edit the ADR, not this file -->"


def write_scoped_rules(store: Store, config: TorsorConfig) -> list:
    """Export the standing rules as *path-scoped* Claude Code rule files under
    .claude/rules/torsor/ — one per ADR, with `paths:` derived from each rule's
    guard scope — so an architecture rule enters context only when the agent
    touches a file it governs, instead of every session via a monolithic
    CLAUDE.md block. Charter principles have no scope and become an unscoped
    file (loaded every session, like CLAUDE.md). The directory is fully
    managed: a file torsor no longer produces is removed."""
    import json
    from pathlib import Path

    _log_op(store, "get_rules", "scoped")
    out_dir = store.paths.claude_rules_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if store.paths.charter.exists():
        principles = _charter_section(store.read_note(store.paths.charter).body, "Non-negotiable principles")
        if principles:
            target = out_dir / "principles.md"
            target.write_text(
                f"# Non-negotiable principles (torsor)\n\n{principles.strip()}\n\n"
                + _SCOPED_PROVENANCE.format(src=".torsor/charter.md") + "\n",
                encoding="utf-8",
            )
            written.append(target)

    for note_path, title, rules in guard.load_rules_by_note(store):
        globs = sorted({_scope_to_paths_glob(r.scope) for r in rules})
        rel = note_path.relative_to(store.paths.root).as_posix()
        target = out_dir / note_path.name
        lines = ["---", "paths:", *(f"  - {json.dumps(g)}" for g in globs), "---", "", f"# {title}", ""]
        lines += [_rule_line(r) for r in rules]
        lines += ["", "Machine-enforced — `torsor guard` flags violations.", "",
                  _SCOPED_PROVENANCE.format(src=rel), ""]
        target.write_text("\n".join(lines), encoding="utf-8")
        written.append(target)

    keep = {p.name for p in written}
    for stale in out_dir.glob("*.md"):
        if stale.name not in keep:
            stale.unlink()
    return written


_PRIMER_START = "<!-- torsor:primer -->"
_PRIMER_END = "<!-- /torsor:primer -->"

_TOKEN_PLAYBOOK = """### Work token-efficiently
- Call `bootstrap_session()` ONCE at session start — never re-call it mid-session. (Skip it entirely when torsor's SessionStart hook already injected the digest.)
- Before reading files to "understand the project", try `recall(query)` / `get_intent(topic)` — prior decisions and the symbol map are already indexed.
- Use `impact(symbol)` instead of repo-wide grep to find callers.
- Don't re-derive what's in this primer; it is current as of the last `torsor primer --write`.
- `remember()` decisions and `handoff()` at session end so the next session skips rediscovery entirely."""


def project_primer(store: Store, config: TorsorConfig, *, max_tokens: int = 800) -> str:
    """Token-saver: a budgeted, prompt-time project primer (what this is, how
    it's shaped, where things live, and token-efficient tool habits). Content
    an agent reads in the prompt file costs zero discovery tool-calls per
    session — the cheapest tokens are the ones never spent."""
    cpt = config.budgets.chars_per_token
    sections: list[str] = []

    for label, path, frac in [
        ("What this project is", store.paths.charter, 0.30),
        ("How it's architected", store.paths.system_patterns, 0.30),
        ("Repo map (key modules)", store.paths.map_overview, 0.20),
    ]:
        if path.exists():
            body = store.read_note(path).body.strip()
            text = truncate_to_tokens(body, int(max_tokens * frac), cpt)
            if text.strip():
                sections.append(f"### {label}\n{text}")

    cmds = list_commands(store)
    if cmds:
        lines = [f"- `{c['command']}`" + (f" — {c['note']}" if c["note"] else f" ({c['name']})") for c in cmds]
        sections.append("### Project commands (don't re-derive these)\n" + "\n".join(lines))

    sections.append(_TOKEN_PLAYBOOK)
    primer = "## Project primer (torsor-helper)\n\n" + "\n\n".join(sections)
    return truncate_to_tokens(primer, max_tokens, cpt)


def write_primer_block(store: Store, config: TorsorConfig, target, *, max_tokens: int = 800) -> str:
    return _write_managed_block(
        target, _PRIMER_START, _PRIMER_END, project_primer(store, config, max_tokens=max_tokens)
    )


_MODELS_START = "<!-- torsor:models -->"
_MODELS_END = "<!-- /torsor:models -->"

# Default op -> tier policy. CHEAP = deterministic torsor lookups + mechanical
# maintenance that return exact answers (no reasoning). SMART = judgement/creation.
_CHEAP_OPS = [
    "recall", "get_intent", "find_files", "impact", "get_rules", "get_primer",
    "check_drift", "check_dependencies", "check_staleness", "verify", "map_repo",
    "consolidate", "list_commands", "recipes",
]
_SMART_WORK = [
    "designing architecture", "writing & refactoring code",
    "making decisions (record_decision)", "debugging novel failures",
]


def model_policy(store: Store, config: TorsorConfig) -> str:
    """A prompt-ready model-routing policy: which work runs on the cheap model vs
    the smart model. torsor declares it; the harness/agent routes by it."""
    cheap = config.models.cheap or "(unset — run: torsor models --cheap <model-id>)"
    smart = config.models.smart or "(unset — run: torsor models --smart <model-id>)"
    lines = [
        "## Model routing (torsor-helper — token thrift)",
        "",
        "Route each task to the cheapest model that can do it *correctly*:",
        "",
        f"- **Cheap model — `{cheap}`** for deterministic torsor lookups & mechanical work "
        f"that return EXACT answers (no reasoning needed): {' · '.join(_CHEAP_OPS)}, and replaying "
        f"recorded commands (`torsor commands --run`). These recur constantly — they don't need a frontier model.",
        f"- **Smart model — `{smart}`** for judgement & creation: {' · '.join(_SMART_WORK)}.",
    ]
    if config.models.fast:
        lines.append(f"- **Fast model — `{config.models.fast}`** for quick mid-tier turns when the cheap model is too weak but a frontier model is overkill.")
    lines += [
        "",
        "Run `torsor verify` (the deterministic guard+deps+staleness gate) on the "
        "cheap model as a loop / pre-commit completion check; route the *fix* after a "
        "failed verdict to the smart model.",
        "",
        "Rule of thumb: if torsor can answer it deterministically, use the cheap model; "
        "if it requires inventing something new, use the smart model.",
    ]
    return "\n".join(lines)


def model_policy_json(store: Store, config: TorsorConfig) -> dict:
    """Machine-readable model-routing policy for programmatic routers (any harness,
    not just prompt-reading agents). The Markdown form (`model_policy`) is for
    agents that read a rules file; this is for code that picks the model itself."""
    return {
        "cheap": config.models.cheap,
        "smart": config.models.smart,
        "fast": config.models.fast,
        "route": {"cheap": list(_CHEAP_OPS), "smart": list(_SMART_WORK)},
        "note": "Run the 'cheap' ops + command replays on the cheap model; reserve 'smart' "
                "for design/code/decisions. torsor declares the policy; the harness routes.",
    }


def write_model_policy(store: Store, config: TorsorConfig, target) -> str:
    return _write_managed_block(target, _MODELS_START, _MODELS_END, model_policy(store, config))


# ---- Command book: learn & replay the project's commands ----

_CMD_RE = _re.compile(r"^- \*\*(.+?)\*\*:\s*`([^`]+)`(?:\s*—\s*(.*))?$")


def list_commands(store: Store) -> list[dict]:
    """The recorded project commands, parsed from .torsor/commands.md."""
    if not store.paths.commands_file.exists():
        return []
    out: list[dict] = []
    for line in store.read_note(store.paths.commands_file).body.splitlines():
        m = _CMD_RE.match(line.strip())
        if m:
            out.append({"name": m.group(1).strip(), "command": m.group(2).strip(), "note": (m.group(3) or "").strip()})
    return out


def record_command(store: Store, name: str, command: str, note: str = "") -> str:
    """Record/update a named project command so it's never re-derived. Persists to
    the committed Markdown command book; surfaces in the primer."""
    cmds = {c["name"]: c for c in list_commands(store)}
    cmds[name] = {"name": name, "command": command, "note": note}
    lines = []
    for n in sorted(cmds):
        c = cmds[n]
        line = f"- **{c['name']}**: `{c['command']}`"
        if c["note"]:
            line += f" — {c['note']}"
        lines.append(line)
    store.write_note(
        store.paths.commands_file,
        Frontmatter(type="commands", tags=["commands"]),
        "Project Commands", "\n".join(lines),
    )
    return str(store.paths.commands_file)


def run_command(store: Store, name: str):
    """Execute a recorded command (returns CompletedProcess, or None if unknown).
    Runs the user-/agent-recorded command via the shell from the repo root."""
    import subprocess

    cmds = {c["name"]: c for c in list_commands(store)}
    found = cmds.get(name)
    if not found:
        return None
    return subprocess.run(found["command"], shell=True, cwd=str(store.paths.root))


# ---- Op frequency log: learn which deterministic lookups recur ----

def _log_op(store: Store, op: str, args: str = "") -> None:
    """Best-effort: record a deterministic-tool call for the 'recipes' view. Never
    creates the index just to log, and never raises (logging must not break a tool)."""
    try:
        if not store.paths.index_db.exists():
            return
        conn = db.connect(store.paths.index_db)
        try:
            db.log_op(conn, op, str(args)[:200])
        finally:
            conn.close()
    except Exception:
        pass


def recipes(store: Store, limit: int = 10) -> list:
    """The most-repeated deterministic lookups — what the agent does over and over,
    i.e. prime candidates to run on the cheap model."""
    if not store.paths.index_db.exists():
        return []
    conn = db.connect(store.paths.index_db)
    try:
        return db.top_ops(conn, limit)
    finally:
        conn.close()


def impact(store: Store, config: TorsorConfig, symbol: str) -> dict:
    """Blast radius of a symbol: who references it, across files, via the
    cartographer's resolved reference edges. Read-only over the existing index
    (run `torsor map` first). Empty when the index/symbol is absent."""
    _log_op(store, "impact", symbol)
    empty = {"symbol": symbol, "callers": [], "count": 0}
    if not store.paths.index_db.exists():
        return empty
    base = symbol.split(".")[-1]
    conn = db.connect(store.paths.index_db)
    try:
        syms = db.search_symbols(conn, base, limit=50)
        exact = [s for s in syms if s.name == symbol]
        matches = exact or [s for s in syms if s.name.split(".")[-1] == base]
        modules = {cartographer.norm_module(s.module) for s in matches}

        callers: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for dotted in modules:
            for caller, module in db.who_references(conn, dotted, base):
                if (caller, module) not in seen:
                    seen.add((caller, module))
                    callers.append({"caller": caller, "module": module})
    finally:
        conn.close()

    callers.sort(key=lambda c: (c["module"], c["caller"]))
    return {"symbol": symbol, "callers": callers, "count": len(callers)}


def connect(store: Store, config: TorsorConfig, source: str, target: str, *, max_hops: int = 12) -> dict:
    """Shortest directed path through the symbol call graph from `source` to
    `target` (who-calls-what), via the cartographer's resolved reference edges.
    Read-only over the existing index (run `torsor map` first). `found` is False
    when the index is absent, either endpoint is unknown, or no directed path
    exists. Bounded by `max_hops` so output stays token-thrifty on dense graphs."""
    _log_op(store, "connect", f"{source} -> {target}")
    empty = {"source": source, "target": target, "path": [], "hops": 0, "found": False}
    if not store.paths.index_db.exists():
        return empty
    src = source.split(".")[-1]
    dst = target.split(".")[-1]

    conn = db.connect(store.paths.index_db)
    try:
        src_syms = [s for s in db.search_symbols(conn, src, limit=50)
                    if s.name.split(".")[-1] == src]
        if not src_syms:
            return empty
        start_module = cartographer.norm_module(src_syms[0].module)
        if src == dst:
            return {"source": source, "target": target,
                    "path": [{"symbol": src, "module": start_module}], "hops": 0, "found": True}
        # adjacency: caller name -> [(referenced_name, resolved_module)]
        adj: dict[str, list[tuple[str, str]]] = {}
        for caller, ref, mod in db.call_graph_edges(conn):
            adj.setdefault(caller, []).append((ref, cartographer.norm_module(mod)))
    finally:
        conn.close()

    # Breadth-first search yields the shortest hop-count path. `prev` doubles as
    # the visited set and records each node's parent + the module it resolved into.
    prev: dict[str, tuple[str | None, str]] = {src: (None, start_module)}
    queue: deque[tuple[str, int]] = deque([(src, 0)])
    while queue:
        node, depth = queue.popleft()
        if node == dst:
            break
        if depth >= max_hops:
            continue
        for ref, mod in adj.get(node, []):
            if ref not in prev:
                prev[ref] = (node, mod)
                queue.append((ref, depth + 1))

    if dst not in prev:
        return empty

    chain: list[dict] = []
    node: str | None = dst
    while node is not None:
        parent, mod = prev[node]
        chain.append({"symbol": node, "module": mod})
        node = parent
    chain.reverse()
    return {"source": source, "target": target, "path": chain, "hops": len(chain) - 1, "found": True}


def get_intent(store: Store, config: TorsorConfig, topic: str | None = None) -> str:
    _log_op(store, "get_intent", topic or "")
    cpt = config.budgets.chars_per_token
    total = config.budgets.bootstrap_tokens
    sections: list[str] = []

    for label, path, frac in [
        ("System Patterns", store.paths.system_patterns, 0.4),
        ("Tech Context", store.paths.tech_context, 0.3),
    ]:
        if path.exists():
            note = store.read_note(path)
            text = truncate_to_tokens(note.body.strip(), int(total * frac), cpt)
            if text.strip():
                sections.append(f"## {label}\n\n{text}")

    if store.paths.decisions_dir.exists():
        titles = []
        for p in sorted(store.paths.decisions_dir.glob("*.md")):
            note = store.read_note(p)
            if note.frontmatter.status == "superseded":  # stale intent — omit
                continue
            titles.append(note.title)
        if titles:
            sections.append("## Decisions\n\n" + "\n".join(f"- {t}" for t in titles))

    if topic and store.paths.index_db.exists():
        conn = db.connect(store.paths.index_db)
        try:
            syms = db.search_symbols(conn, topic, limit=8)
        finally:
            conn.close()
        if syms:
            lines = [f"- `{s.signature}` ({s.kind}) — {s.module}:{s.line}" for s in syms]
            sections.append("## Relevant existing symbols\n\n" + "\n".join(lines))

    return "\n\n".join(sections)


def _next_adr_number(store) -> int:
    nums = []
    if store.paths.decisions_dir.exists():
        for p in store.paths.decisions_dir.glob("*.md"):
            m = _re.match(r"(\d+)", p.name)
            if m:
                nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def _slug(title: str) -> str:
    s = _re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s or "decision"


def _find_adr(store, ref):
    """Resolve an ADR by full stem ('0002-foo'), file name, or leading number ('0002'/'2')."""
    if not store.paths.decisions_dir.exists():
        return None
    ref = str(ref)
    for p in sorted(store.paths.decisions_dir.glob("*.md")):
        if p.stem == ref or p.name == ref or p.stem.startswith(ref + "-"):
            return p
        m = _re.match(r"(\d+)", p.name)
        if m and m.group(1).lstrip("0") == ref.lstrip("0"):
            return p
    return None


def record_decision(store, title, context, decision, consequences="", rules=None, supersedes=None) -> str:
    number = _next_adr_number(store)
    new_stem = f"{number:04d}-{_slug(title)}"

    fm_data = {"type": "decision", "status": "accepted", "tags": ["adr"], "rules": rules or []}
    if supersedes:
        old = _find_adr(store, supersedes)
        if old is not None:
            old_note = store.read_note(old)
            old_data = old_note.frontmatter.model_dump(exclude_none=True)
            old_data["status"] = "superseded"
            old_data["superseded_by"] = new_stem
            store.write_note(old, Frontmatter.model_validate(old_data), old_note.title, old_note.body)
            fm_data["supersedes"] = old.stem

    body = (
        f"## Context\n{context}\n\n"
        f"## Decision\n{decision}\n\n"
        f"## Consequences\n{consequences}\n"
    )
    target = store.paths.decisions_dir / f"{new_stem}.md"
    store.write_note(target, Frontmatter.model_validate(fm_data), f"ADR {number:04d}: {title}", body)
    return str(target)


# Extensions the default git-changed discovery feeds to guard/deps. Non-Python
# files only ever match forbid_pattern rules scoped to them (AST checkers and
# the deps check no-op gracefully on non-Python sources).
_SOURCE_EXTS = (".py", ".pyi", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".go", ".rs")


def list_practices(store, config, language=None) -> str:
    """Render the curated best-practice pack(s): one language, or every pack
    detected in the repo when language is None."""
    from torsor_helper import practices as _practices

    if language is None:
        detected = _practices.detect_languages(store.paths.root)
        if not detected:
            return "No supported languages detected. Available packs: " + ", ".join(
                _practices.available_languages()
            )
        return "\n\n".join(_practices.render(lang) for lang in detected)
    try:
        return _practices.render(language)
    except KeyError:
        return f"Unknown pack {language!r}. Available: " + ", ".join(_practices.available_languages())


def adopt_practices(store, config, language) -> dict:
    """Adopt a best-practice pack: records ONE ADR carrying the pack's
    machine-readable rules (guard enforces them) + prose principles."""
    from torsor_helper import practices as _practices

    try:
        payload = _practices.adr_payload(language)
    except KeyError:
        return {
            "adopted": False,
            "message": f"Unknown pack {language!r}. Available: "
                       + ", ".join(_practices.available_languages()),
        }
    slug = _slug(payload["title"])
    if store.paths.decisions_dir.exists():
        for existing in store.paths.decisions_dir.glob("*.md"):
            if slug in existing.stem:
                return {"adopted": False, "message": f"Already adopted: {existing} (edit or supersede it instead)."}
    path = record_decision(store, **payload)
    return {
        "adopted": True,
        "path": path,
        "message": (
            f"Adopted the {language} pack → {path}\n"
            "Next: `torsor guard --update-baseline` to grandfather existing code, "
            "then `torsor rules --write AGENTS.md` to refresh the prompt block."
        ),
    }


def _rel_to_root(root, toplevel, files) -> list[str]:
    """Re-anchor git toplevel-relative paths to the torsor root, keeping only
    source files that live under it — so a .torsor/ in a subdirectory of the git
    repo never checks the wrong paths. Shared by the working-tree and per-commit
    change discovery."""
    from pathlib import Path

    top, base = Path(toplevel), Path(root).resolve()
    out: list[str] = []
    for f in files:
        if not f.endswith(_SOURCE_EXTS):
            continue
        try:
            out.append((top / f).relative_to(base).as_posix())
        except ValueError:
            continue  # outside the torsor root — not ours to check
    return out


def _git_changed(root) -> list[str]:
    import subprocess

    try:
        toplevel = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        changed = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.split()
        untracked = subprocess.run(
            # --full-name: toplevel-relative like `diff --name-only`, regardless
            # of where inside the repo the torsor root sits
            ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard", "--full-name"],
            capture_output=True, text=True, timeout=10,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return []
    if not toplevel:
        return []
    return _rel_to_root(root, toplevel, changed + untracked)


def _git_changed_in_commit(root, ref="HEAD") -> list[str]:
    """Source files touched by a single commit (default HEAD) — what the
    post-commit hook remaps. Working-tree `_git_changed` diffs uncommitted state;
    this diffs the commit itself."""
    import subprocess

    try:
        toplevel = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        names = subprocess.run(
            ["git", "-C", str(root), "diff-tree", "--no-commit-id", "--name-only", "-r", ref],
            capture_output=True, text=True, timeout=10,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return []
    if not toplevel:
        return []
    return _rel_to_root(root, toplevel, names)


def check_drift(store, config, files=None) -> list:
    _log_op(store, "check_drift", "")
    if files is None:
        files = _git_changed(store.paths.root)
    return guard.check_drift(store, files)


def new_drift(store, config, files=None) -> list:
    """Drift beyond the committed baseline — the genuinely-new violations."""
    from torsor_helper import baseline as _baseline

    violations = check_drift(store, config, files)
    return _baseline.new_violations(violations, _baseline.load(store.paths.baseline_file))


def guard_run(store, config, files=None, *, update_baseline=False, strict=False, severity=None) -> dict:
    """The single guard orchestration both adapters share: check drift, apply
    the baseline ratchet, and decide strict failure — so the MCP tool and the
    CLI command can't diverge in behavior."""
    from torsor_helper import baseline as _baseline

    violations = check_drift(store, config, files)
    if update_baseline:
        _baseline.save(store.paths.baseline_file, violations)
        return {"violations": violations, "new": [], "baselined": len(violations),
                "failed": False, "updated_baseline": True}
    new = _baseline.new_violations(violations, _baseline.load(store.paths.baseline_file))
    failed = bool(strict and guard.strict_failures(new, severity))
    return {"violations": violations, "new": new, "baselined": len(violations) - len(new),
            "failed": failed, "updated_baseline": False}


def check_dependencies(store, config, files=None) -> list:
    """Flag imports that resolve to no known package (possible slopsquatting).
    Defaults to git-changed files; fully offline."""
    _log_op(store, "check_dependencies", "")
    from torsor_helper import deps as _deps

    if files is None:
        files = _git_changed(store.paths.root)
    return _deps.unknown_imports(store.paths.root, files)


def _verify_check(name, ok, status, reasons) -> dict:
    return {"name": name, "ok": ok, "status": status, "reasons": reasons, "count": len(reasons)}


def _verify_tests(store) -> dict:
    """Run a recorded `test` (or `verify`) command if one exists; skip — never
    fail — when none is recorded, so the default gate stays instant static analysis."""
    names = {c["name"] for c in list_commands(store)}
    target = "test" if "test" in names else ("verify" if "verify" in names else None)
    if target is None:
        return _verify_check("tests", True, "skip", ["no 'test' command recorded (torsor commands --record)"])
    proc = run_command(store, target)
    code = getattr(proc, "returncode", None)
    ok = code == 0
    return _verify_check("tests", ok, "pass" if ok else "fail",
                         [] if ok else [f"`{target}` command exited {code}"])


def verify(store, config, files=None, *, severity=None, run_tests=False) -> dict:
    """The single deterministic verification gate: guard (new drift) + deps
    (slopsquatting) + staleness, and optionally a recorded test command. Composes
    the existing cores — no new checking logic — into one machine-checkable verdict
    designed as a loop-engineering / Stop-hook / CI completion condition.

    `files` defaults to git-changed so guard/deps judge the same change set (fast,
    offline). `ok` is the single boolean a gate reads; per-check `reasons` give the
    agent a fix list without re-running each tool."""
    _log_op(store, "verify", "")
    if files is None:
        files = _git_changed(store.paths.root)

    guard = guard_run(store, config, files, strict=True, severity=severity)
    guard_reasons = [f"{v.file}:{v.line} — [{v.severity}] {v.message} (per {v.source})" for v in guard["new"]]
    dep_findings = check_dependencies(store, config, files)
    dep_reasons = [f"{f['file']}:{f['line']} — unknown import '{f['name']}'" for f in dep_findings]
    stale_findings = check_staleness(store, config)["findings"]
    stale_reasons = [f"[{r.kind}] {r.message}" for r in stale_findings]

    checks = [
        _verify_check("guard", not guard["failed"], "pass" if not guard["failed"] else "fail", guard_reasons),
        _verify_check("deps", not dep_findings, "pass" if not dep_findings else "fail", dep_reasons),
        _verify_check("staleness", not stale_findings, "pass" if not stale_findings else "fail", stale_reasons),
    ]
    if run_tests:
        checks.append(_verify_tests(store))

    ok = all(c["ok"] for c in checks)
    summary = " ".join(f"{c['name']}:{c['status'] if c['status'] != 'fail' else str(c['count'])}" for c in checks)
    return {"ok": ok, "exit_code": 0 if ok else 1, "checks": checks, "summary": summary}


def recommend(store, config, context=None, limit=8):
    conn = _open_index(store, config)
    embedder = _embedder_for(config) if conn is not None else None
    try:
        return coach_report.assemble(store, config, context=context, limit=limit, conn=conn, embedder=embedder)
    finally:
        if conn is not None:
            conn.close()


def dismiss_recommendation(store, key) -> None:
    state = CoachState(store.paths.index_dir / "coach_state.json")
    state.dismiss(key)
    state.save()


def check_staleness(store, config, *, mark=False, unmark=False) -> dict:
    """Detect memory that contradicts current code — dangling [[wikilinks]] and
    dead file-path references (deterministic, index-free, high-precision). Read-only
    by default; `--mark` sets `status: stale` on the offending notes (opt-in,
    reversible via `--unmark`), never touching the note body (ADR 0010)."""
    from torsor_helper.coach import staleness as _staleness

    _log_op(store, "check_staleness", "")
    findings = _staleness.run_staleness(store)
    counts: dict[str, int] = {}
    for r in findings:
        counts[r.kind] = counts.get(r.kind, 0) + 1

    marked: list[str] = []
    if unmark:
        marked = _set_note_status(store, sorted({_note_rel(store, p) for p in _stale_notes(store)}), "active")
    elif mark:
        marked = _set_note_status(store, sorted({r.source for r in findings}), "stale")
    return {"findings": findings, "counts": counts, "marked": marked}


def _stale_notes(store):
    for path in store.iter_note_paths():
        try:
            if store.read_note(path).frontmatter.status == "stale":
                yield path
        except (OSError, UnicodeDecodeError):
            continue


def _note_rel(store, path) -> str:
    try:
        return path.relative_to(store.paths.root).as_posix()
    except ValueError:
        return str(path)


def _set_note_status(store, rels: list[str], status: str) -> list[str]:
    """Rewrite each note's frontmatter `status`, preserving body + other fields
    (mirrors the record_decision supersede rewrite). Returns the notes changed."""
    changed: list[str] = []
    for rel in rels:
        path = store.paths.root / rel
        if not path.exists():
            continue
        note = store.read_note(path)
        if note.frontmatter.status == status:
            continue
        data = note.frontmatter.model_dump(exclude_none=True)
        data["status"] = status
        store.write_note(path, Frontmatter.model_validate(data), note.title, note.body)
        changed.append(rel)
    return changed


def clean(store, config, *, apply: bool = False, deep: bool = False) -> dict:
    """Reclaim derived and expired torsor artefacts. Dry-run by default: without
    `apply` nothing is touched and the returned stats describe what *would* go.
    Never removes a stable tier (charter/architecture/active/insights) or any
    source file — `cleaner` only ever targets orphaned map notes, dead index
    rows, journals past the retention window, and (with `deep`) the whole index."""
    _log_op(store, "clean", f"apply={apply} deep={deep}")
    proposed = cleaner.plan(store, config, deep=deep)
    stats = {
        "dry_run": not apply,
        "map_orphans": len(proposed.map_orphans),
        "journals_expired": len(proposed.journal_expired),
        "dead_rows": sum(proposed.dead_rows.values()),
        "deep": bool(proposed.deep_paths),
        "reclaimed_bytes": proposed.reclaimed_bytes,
        "insights_mined": 0,
        "notes": list(proposed.notes),
        "files": [str(p.relative_to(store.paths.root)) for p in proposed.files],
    }
    if apply:
        stats.update(cleaner.apply(store, config, proposed))
        stats["dry_run"] = False
    return stats


def consolidate(store, config) -> dict:
    written = coach_mining.mine_insights(store)
    duplicates = coach_mining.find_duplicate_entries(store)

    # consolidate is a maintenance pass: index once, directly, so the `indexed`
    # count reflects the freshly-mined insights. (Using _open_index here would
    # reindex internally first, leaving this explicit call to report 0.)
    conn = db.connect(store.paths.index_db)
    try:
        indexed = reindex(store, conn, _embedder_for(config))["indexed"]
        top_accessed = db.top_accessed(conn, limit=3)
    finally:
        conn.close()

    # Snapshot complexity so the Coach can report regressions *since this pass*.
    _snapshot_complexity(store)

    return {
        "insights": len(written),
        "duplicates": len(duplicates),
        "indexed": indexed,
        "top_accessed": top_accessed,
    }


def _snapshot_complexity(store) -> None:
    """Refresh the per-file complexity baseline `coach/trend.find_regressions`
    diffs against. Shared by `consolidate` and the post-commit auto-capture hook,
    so a regression baseline stays fresh with zero manual maintenance calls."""
    from torsor_helper.coach import trend as coach_trend

    if not store.paths.index_db.exists():
        return
    conn = db.connect(store.paths.index_db)
    try:
        db.save_complexity_snapshot(conn, coach_trend.current_complexity(store.paths.root))
    finally:
        conn.close()


# ---- Auto-capture hooks: memory that captures itself on the git / agent
# lifecycle. torsor is never the scheduler (no daemon) — git and Claude Code
# invoke `torsor hooks run <event>`, which dispatches into the cores below.
# Every core is deterministic, offline, and flag-guarded (config.automation).

def _capture_state_path(store):
    # Disposable session bookkeeping, NOT source of truth — lives under .index/.
    return store.paths.index_dir / "capture_state.json"


def _load_capture_state(store) -> dict:
    import json

    try:
        data = json.loads(_capture_state_path(store).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_capture_state(store, data: dict) -> None:
    import json

    path = _capture_state_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _git_out(root, *args) -> str:
    import subprocess

    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _git_head(root) -> str:
    return _git_out(root, "rev-parse", "HEAD")


def _op_totals(store) -> dict:
    if not store.paths.index_db.exists():
        return {}
    conn = db.connect(store.paths.index_db)
    try:
        return db.op_totals(conn)
    finally:
        conn.close()


def _op_delta(store, snapshot: dict) -> list[tuple[str, int]]:
    """Per-op hit increase since the last snapshot — a best-effort, deterministic
    'what ran this session' (op_log is aggregate, not session-scoped: db.py)."""
    cur = _op_totals(store)
    out = [(op, cur[op] - int(snapshot.get(op, 0))) for op in cur]
    out = [(op, n) for op, n in out if n > 0]
    out.sort(key=lambda t: (-t[1], t[0]))
    return out


def _adrs_between(store, prev: int, cur: int) -> list[str]:
    if cur <= prev or not store.paths.decisions_dir.exists():
        return []
    out = []
    for p in sorted(store.paths.decisions_dir.glob("*.md")):
        m = _re.match(r"(\d+)", p.name)
        if m and prev < int(m.group(1)) <= cur:
            out.append(p.stem)
    return out


def _read_md_section(text: str, header: str) -> str:
    """Body under a `## header` up to the next `## ` (or EOF). Empty when absent."""
    m = _re.search(rf"(?m)^##\s+{_re.escape(header)}\s*$", text)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = _re.search(r"(?m)^##\s+", rest)
    return (rest[: nxt.start()] if nxt else rest).strip()


def _find_file_paths(obj) -> list[str]:
    """Recursively collect `file_path` string values from a parsed transcript
    event — generic so a Claude Code schema tweak can't break it."""
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "file_path" and isinstance(v, str):
                found.append(v)
            else:
                found.extend(_find_file_paths(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_find_file_paths(item))
    return found


def _transcript_digest(transcript_path) -> str:
    import json
    from pathlib import Path

    try:
        raw = Path(transcript_path).read_text(encoding="utf-8")
    except OSError:
        return ""
    files: list[str] = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        for fp in _find_file_paths(event):
            if fp not in files:
                files.append(fp)
    if not files:
        return ""
    return "Files touched this session:\n" + "\n".join(f"- {f}" for f in files[:20])


def auto_handoff(store, config, *, session_id=None, transcript_path=None) -> str | None:
    """Write a deterministic end-of-session handoff (no LLM) from git history +
    the op-log delta + new ADRs + the agent's own active-context/progress, so the
    agent never has to call handoff() by hand. Writes nothing (returns None) when
    disabled or when nothing changed — avoids empty handoffs."""
    if not config.automation.auto_handoff:
        return None
    root = store.paths.root
    state = _load_capture_state(store)
    last_head = state.get("last_head") or ""
    head = _git_head(root)

    commit_lines: list[str] = []
    diffstat = ""
    if head and last_head and last_head != head:
        log = _git_out(root, "log", "--oneline", f"{last_head}..{head}")
        commit_lines = [ln for ln in log.splitlines() if ln.strip()]
        diffstat = _git_out(root, "diff", "--shortstat", f"{last_head}..{head}")
    worktree = _git_changed(root)
    worktree_stat = _git_out(root, "diff", "--shortstat")
    op_delta = _op_delta(store, state.get("op_snapshot") or {})
    prev_adr = int(state.get("adr_max") or 0)
    cur_adr = _next_adr_number(store) - 1
    new_adrs = _adrs_between(store, prev_adr, cur_adr)

    if not commit_lines and not worktree and not op_delta and not new_adrs:
        return None

    bits: list[str] = []
    if commit_lines:
        bits.append(f"{len(commit_lines)} commit(s)")
    if diffstat:
        bits.append(diffstat)
    elif worktree_stat:
        bits.append(f"uncommitted: {worktree_stat}")
    if op_delta:
        bits.append("ran " + ", ".join(f"{n}× {op}" for op, n in op_delta))
    summary = "; ".join(bits) or "session activity"
    if commit_lines:
        summary += "\n\nCommits:\n" + "\n".join(f"- {c}" for c in commit_lines[:20])
    if config.automation.parse_transcript and transcript_path:
        extra = _transcript_digest(transcript_path)
        if extra:
            summary += f"\n\n{extra}"

    active_text = store.read_note(store.paths.active_context).body if store.paths.active_context.exists() else ""
    open_qs = _read_md_section(active_text, "Open questions")
    next_steps = store.read_note(store.paths.progress).body.strip() if store.paths.progress.exists() else ""

    path = record_handoff(store, summary, decisions=", ".join(new_adrs),
                          open_questions=open_qs, next_steps=next_steps)

    _save_capture_state(store, {
        "last_head": head or last_head,
        "op_snapshot": _op_totals(store),
        "adr_max": cur_adr,
    })
    return path


def on_commit(store, config) -> dict:
    """Post-commit hook core: partial-map the just-committed source files (the
    ADR 0008 merge — zero new mapping code) and refresh the complexity baseline,
    so the graph and regression signal stay fresh with no manual map/consolidate.
    Best-effort; writes only .torsor/ Markdown + the disposable index, never commits."""
    result = {"mapped": [], "snapshot": False}
    changed = _git_changed_in_commit(store.paths.root, "HEAD")
    if not changed:
        return result
    if config.automation.auto_map_on_commit:
        map_repo(store, config, paths=changed)
        result["mapped"] = changed
    if config.automation.auto_snapshot_on_commit:
        _snapshot_complexity(store)
        result["snapshot"] = store.paths.index_db.exists()
    return result


def pre_push(store, config) -> dict:
    """Pre-push hook core: advisory guard. Installed only when guard_on_push is
    on; the adapter maps `failed` to the process exit code so a failing guard can
    block the push. A no-op verdict when disabled."""
    if not config.automation.guard_on_push:
        return {"failed": False, "new": [], "skipped": True}
    result = guard_run(store, config, strict=True)
    return {"failed": result["failed"], "new": result["new"], "skipped": False}


def install_hooks(store, config, *, git=True, claude=True, local=False, on_stop=False) -> dict:
    """Wire git hooks + Claude Code hook entries so capture fires on the lifecycle.
    Idempotent, foreign-content-preserving, and CLI-only (footgun parity with the
    self-updater — an agent should not rewrite its own hooks; ADR 0009)."""
    import json

    from torsor_helper import hooks as _hooks

    root = str(store.paths.root)
    result = {"git_hooks": [], "claude_settings": None, "warnings": [], "skipped": []}

    if git:
        hooks_dir = _hooks.resolve_hooks_dir(root)
        if hooks_dir is None:
            result["warnings"].append("not a git repo — git hooks skipped")
            result["skipped"].append("git")
        else:
            foreign = _hooks.foreign_hook_manager(root)
            if foreign:
                result["warnings"].append(
                    f"{foreign} manages git hooks here — add "
                    f'`torsor hooks run post-commit --root \"{root}\"` to your {foreign} '
                    "config instead of relying on .git/hooks"
                )
            pc = _hooks.write_git_hook(hooks_dir, "post-commit", _hooks.post_commit_script(root))
            result["git_hooks"].append(str(pc))
            if config.automation.guard_on_push:
                pp = _hooks.write_git_hook(hooks_dir, "pre-push", _hooks.pre_push_script(root))
                result["git_hooks"].append(str(pp))

    if claude:
        target = store.paths.claude_settings_local if local else store.paths.claude_settings
        data: dict = {}
        if target.exists():
            try:
                loaded = json.loads(target.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except ValueError:
                data = {}
        merged = _hooks.merge_settings_hooks(data, root=".", on_stop=on_stop)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        result["claude_settings"] = str(target)

    # Baseline the capture marker at install time so the first auto-handoff is
    # scoped to post-install activity (not a dump of all prior commits/ADRs).
    if not _capture_state_path(store).exists():
        _save_capture_state(store, {
            "last_head": _git_head(root),
            "op_snapshot": _op_totals(store),
            "adr_max": _next_adr_number(store) - 1,
        })
    return result


def uninstall_hooks(store, config, *, local=False) -> dict:
    """Remove only torsor-owned git hooks + Claude Code hook entries."""
    import json

    from torsor_helper import hooks as _hooks

    result = {"removed": [], "claude_settings": None}
    hooks_dir = _hooks.resolve_hooks_dir(str(store.paths.root))
    if hooks_dir is not None:
        for name in ("post-commit", "pre-push"):
            removed = _hooks.write_git_hook(hooks_dir, name, "", remove=True)
            if removed is not None:
                result["removed"].append(str(removed))

    target = store.paths.claude_settings_local if local else store.paths.claude_settings
    if target.exists():
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
            data = loaded if isinstance(loaded, dict) else {}
        except ValueError:
            data = {}
        merged = _hooks.merge_settings_hooks(data, remove=True)
        target.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        result["claude_settings"] = str(target)
    return result


def hooks_status(store, config) -> dict:
    """Read-only report of which git hooks + Claude Code events carry a torsor
    entry. The only auto-capture surface exposed as an MCP tool (writes are CLI-only)."""
    import json

    from torsor_helper import hooks as _hooks

    status = {"git_repo": False, "git_hooks": {}, "claude_events": []}
    hooks_dir = _hooks.resolve_hooks_dir(str(store.paths.root))
    if hooks_dir is not None:
        status["git_repo"] = True
        for name in ("post-commit", "pre-push"):
            f = hooks_dir / name
            status["git_hooks"][name] = f.exists() and _hooks.is_managed_git_hook(f.read_text(encoding="utf-8"))

    events: list[str] = []
    for target in (store.paths.claude_settings, store.paths.claude_settings_local):
        if not target.exists():
            continue
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        events.extend(_hooks.settings_events_with_torsor(data))
    status["claude_events"] = sorted(set(events))
    return status
