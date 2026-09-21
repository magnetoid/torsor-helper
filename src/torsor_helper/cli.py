from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from torsor_helper import db
from torsor_helper import operations as ops
from torsor_helper import render
from torsor_helper.clients import SUPPORTED_CLIENTS, config_location, config_snippet, instructions_file
from torsor_helper.config import TorsorConfig, load_config, save_config
from torsor_helper.embeddings import get_embedder
from torsor_helper.indexer import reindex
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

app = typer.Typer(help="torsor-helper: persistent memory + architectural intent over MCP.")


def _resolve_block_target(root: Path, write: Optional[Path], client: Optional[str]) -> Optional[Path]:
    """Resolve where a managed block (rules/primer/model policy) should be written:
    an explicit --write path wins; else --client's conventional instructions file
    (AGENTS.md by default). Returns None when neither was given. Exits on bad client."""
    if write is not None:
        return write if write.is_absolute() else root / write
    if client is not None:
        if client not in SUPPORTED_CLIENTS:
            typer.echo(f"Unknown client {client!r}. Known: {', '.join(SUPPORTED_CLIENTS)}", err=True)
            raise typer.Exit(code=1)
        return root / instructions_file(client)
    return None


def _version_callback(value: bool) -> None:
    if value:
        from torsor_helper import __version__

        typer.echo(f"torsor-helper {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", help="Show the torsor-helper version and exit.",
        callback=_version_callback, is_eager=True,
    ),
) -> None:
    """torsor-helper: persistent memory + architectural intent over MCP."""


def _load(root: Path, *, config: bool = True):
    """(paths, config, store) for a command, or exit 1 if the project is not
    initialized. Every command needs exactly this, and copy-pasting it 21 times
    is how `recipes` ended up skipping load_config and silently diverging.

    `config=False` keeps the two commands that never read torsor.toml working on
    a project whose config is malformed — they have no reason to care.
    """
    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    return tp, (load_config(tp) if config else None), Store(tp)


def _check_severity(value):
    """Reject a typo instead of widening the gate. An unknown threshold mapped
    to cutoff 0 — "fail on anything" — which is the opposite of conservative
    and invisible in CI."""
    from torsor_helper.guard import SEVERITIES

    if value is not None and value not in SEVERITIES:
        typer.echo(
            f"Unknown --severity {value!r}. Expected one of: {', '.join(SEVERITIES)}.", err=True
        )
        raise typer.Exit(code=2)
    return value


def _emit(payload, as_json: bool) -> bool:
    """Print `payload` as JSON when asked. Returns True when it did, so a caller
    can skip its prose rendering: `if _emit(x, as_json): return`."""
    if not as_json:
        return False
    import json

    typer.echo(json.dumps(payload, default=str))
    return True


@app.command()
def init(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root to scaffold .torsor/ in."),
    client: Optional[str] = typer.Option(None, help=f"Print MCP config for: {', '.join(SUPPORTED_CLIENTS)}"),
    write: bool = typer.Option(False, "--write", help="Write/merge a project .mcp.json so clients (Claude Code, Cursor, ...) auto-detect torsor-helper."),
    force: bool = typer.Option(False, help="Overwrite existing seed files."),
) -> None:
    """Scaffold the .torsor/ pyramid and write torsor.toml."""
    paths = TorsorPaths(root)
    # Validate input before any filesystem side effects.
    if client and client not in SUPPORTED_CLIENTS:
        typer.echo(f"Unknown client {client!r}. Known: {', '.join(SUPPORTED_CLIENTS)}", err=True)
        raise typer.Exit(code=1)
    Store(paths).scaffold(force=force)
    if not paths.config_file.exists() or force:
        save_config(paths, TorsorConfig())
    typer.echo(f"Initialized torsor-helper at {paths.base}")
    if write:
        from torsor_helper.clients import write_mcp_json

        target = write_mcp_json(root, str(root.resolve()))
        typer.echo(f"Wrote {target} — MCP clients that read .mcp.json (e.g. Claude Code) will auto-detect torsor-helper.")
    if client:
        location = config_location(client)
        where = f" — goes in: {location}" if location else ""
        typer.echo(f"\n# MCP config for {SUPPORTED_CLIENTS[client]}{where}\n")
        typer.echo(config_snippet(client, root=str(root.resolve())))


_LOOPBACK = ("127.0.0.1", "localhost", "::1", "::ffff:127.0.0.1")


@app.command()
def mcp(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    http: bool = typer.Option(False, "--http", help="Serve over HTTP (streamable-http) instead of stdio — for shared/remote/team use."),
    host: str = typer.Option("127.0.0.1", help="Host to bind when --http."),
    port: int = typer.Option(8000, help="Port to bind when --http."),
    allow_remote: bool = typer.Option(False, "--allow-remote", help="Required to bind --http to a non-loopback host; the transport has no authentication."),
) -> None:
    """Run the torsor-helper MCP server (stdio by default; --http for a shared service)."""
    from torsor_helper.server import run

    if http and host not in _LOOPBACK and not allow_remote:
        # A warning the user could ignore was not a gate: this serves read AND
        # write access to the project's memory, unauthenticated, to anyone who
        # can reach the port.
        typer.echo(
            f"Refusing to bind the HTTP transport to {host}: it has no authentication, so this "
            "would expose read/write access to this project's memory to anyone who can reach "
            "the port. Put it behind a reverse proxy or an SSH tunnel, or pass --allow-remote "
            "if you accept that.",
            err=True,
        )
        raise typer.Exit(code=2)
    run(root, transport="streamable-http" if http else "stdio", host=host, port=port)


@app.command()
def update(
    print_only: bool = typer.Option(False, "--print-only", help="Show the upgrade command without running it."),
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt."),
) -> None:
    """Update the torsor CLI itself (detects uv tool / pipx / pip installs)."""
    import subprocess

    from torsor_helper import updater

    method = updater.detect_install_method()
    cmd = updater.update_command(method)
    if cmd is None:
        typer.echo(updater.manual_hint(method))
        return
    typer.echo(f"Detected install method: {method}")
    typer.echo("$ " + " ".join(cmd))
    if print_only:
        return
    # This replaces the running binary with whatever the package index — or a git
    # branch HEAD — currently serves, with no signature check. Confirm it.
    if not yes and not typer.confirm("Run it?", default=True):
        typer.echo("Cancelled.")
        return
    result = subprocess.run(cmd)
    if result.returncode != 0:
        typer.echo("Update failed — run the command above manually.", err=True)
        raise typer.Exit(code=result.returncode)
    typer.echo("Updated. Check with: torsor --version")


@app.command()
def doctor(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root to check."),
    as_json: bool = typer.Option(False, "--json", help="Emit the structured verdict."),
) -> None:
    """Check whether this project is healthy — and whether the parts that fail
    quietly are working: a stale index, semantic recall silently on the hashing
    fallback, hooks that were never installed, an ADR rule that does not parse."""
    paths = TorsorPaths(root)
    checks: list[dict] = []

    def check(name, ok, detail, *, warn=False):
        checks.append({"name": name, "status": "warn" if warn and not ok else ("ok" if ok else "fail"),
                       "detail": detail})
        return ok

    missing = [p.name for p in (paths.charter, paths.system_patterns, paths.active_context, paths.progress)
               if not p.exists()]
    if not paths.base.exists():
        check("layout", False, f"not initialized: no .torsor/ at {root} — run `torsor init`")
        _doctor_report(checks, as_json)
        raise typer.Exit(code=1)
    check("layout", not missing, "seed files present" if not missing else f"missing: {', '.join(missing)}")

    try:
        config = load_config(paths)
        check("config", True, str(paths.config_file))
    except Exception as exc:
        check("config", False, f"{paths.config_file}: {exc}")
        _doctor_report(checks, as_json)
        raise typer.Exit(code=1)

    store = Store(paths)
    _doctor_index(paths, store, config, check)
    _doctor_languages(check)
    _doctor_git_and_hooks(store, config, check)
    _doctor_rules(store, check)

    _doctor_report(checks, as_json)
    if any(c["status"] == "fail" for c in checks):
        raise typer.Exit(code=1)


def _doctor_index(paths, store, config, check) -> None:
    from torsor_helper import cartographer, db

    if not paths.index_db.exists():
        check("index", True, "not built yet (recall builds it on demand)", warn=True)
        check("map", True, "not built yet — run `torsor map`", warn=True)
        return
    size = paths.index_db.stat().st_size
    conn = db.connect(paths.index_db)
    try:
        stamp = db.meta_get(conn, "map_fingerprint")
        notes = db.note_count(conn)
    finally:
        conn.close()
    check("index", True, f"{notes} note(s), {size / 1e6:.1f} MB")
    if stamp is None:
        check("map", True, "never fully mapped — run `torsor map`", warn=True)
    else:
        current = stamp == cartographer.repo_fingerprint(paths.root)
        check("map", current, "current" if current else "stale — run `torsor map`", warn=True)


def _doctor_languages(check) -> None:
    from torsor_helper import languages
    from torsor_helper.embeddings import get_embedder
    from torsor_helper.config import TorsorConfig

    name = get_embedder(TorsorConfig()).name
    check("embeddings", name != "hashing",
          "fastembed" if name != "hashing"
          else "using the hashing fallback — recall is lexical only; "
               "install torsor-helper[embeddings] for semantic search",
          warn=True)
    avail = languages.available()
    # Name each one: "some languages missing" does not tell you which extra to
    # install, and the per-language line is what the map summary echoes too.
    detail = "; ".join(
        f"{name}: {'ready' if ok else 'install torsor-helper[languages]'}"
        for name, ok in sorted(avail.items())
    )
    check("languages", all(avail.values()), detail, warn=True)


def _doctor_git_and_hooks(store, config, check) -> None:
    from torsor_helper import gitinfo

    repo = gitinfo.is_repo(store.paths.root)
    check("git", repo, "repository detected" if repo
          else "not a git repository — churn, coupling and auto-capture are off", warn=True)
    status = ops.hooks_status(store, config)
    on = [n for n, enabled in status["git_hooks"].items() if enabled]
    events = status["claude_events"]
    check("hooks", bool(on or events),
          f"git: {', '.join(on) or 'none'}; claude: {', '.join(events) or 'none'}"
          if (on or events) else "none installed — run `torsor hooks install`", warn=True)


def _doctor_rules(store, check) -> None:
    from torsor_helper import guard

    by_note = guard.load_rules_by_note(store)
    errors = getattr(guard.load_rules_by_note, "errors", [])
    total = sum(len(rules) for _, _, rules in by_note)
    if errors:
        detail = "; ".join(f"{p.name}: {msg}" for p, msg in errors[:3])
        check("rules", False, f"{len(errors)} rule(s) did not parse and are NOT enforced — {detail}", warn=True)
    else:
        check("rules", True, f"{total} machine-enforced rule(s) across {len(by_note)} note(s)")


def _doctor_report(checks, as_json) -> None:
    ok = not any(c["status"] == "fail" for c in checks)
    if _emit({"ok": ok, "checks": checks}, as_json):
        return
    for c in checks:
        mark = {"ok": "ok  ", "warn": "warn", "fail": "FAIL"}[c["status"]]
        typer.echo(f"{mark}  {c['name']}: {c['detail']}")
    typer.echo("\n" + ("OK: torsor-helper project is healthy."
                        if ok else "Problems found — see FAIL above."))


# ---- Memory: the same seven operations the MCP server exposes -------------
# These were MCP-only, including the five founding tools, although nearly every
# feature is meant to be both (CLAUDE.md). Without them memory cannot be
# scripted, used from CI, or debugged without an MCP client attached.


@app.command()
def recall(
    query: list[str] = typer.Argument(..., help="What to search memory for."),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    limit: int = typer.Option(8, "--limit", help="Maximum hits."),
    type_: Optional[str] = typer.Option(None, "--type", help="Only notes of this frontmatter type (e.g. decision)."),
    kind: Optional[str] = typer.Option(None, "--kind", help="Only notes of this kind (e.g. learning)."),
    include_superseded: bool = typer.Option(False, "--include-superseded", help="Include superseded decisions."),
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable hits."),
) -> None:
    """Hybrid search across memory, wiki and map — ranked snippets, token-budgeted."""
    _, config, store = _load(root)
    result = ops.recall(store, config, " ".join(query), limit=limit, type_=type_, kind=kind,
                        include_superseded=include_superseded)
    if _emit({"query": result.query, "total_tokens": result.total_tokens,
              "hits": [h.model_dump(mode="json") for h in result.hits]}, as_json):
        return
    if not result.hits:
        typer.echo(f"No matches for {' '.join(query)!r}.")
        return
    for hit in result.hits:
        typer.echo(render.recall_hit(hit))
        typer.echo("")


@app.command()
def remember(
    content: list[str] = typer.Argument(..., help="What to remember."),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    kind: str = typer.Option("observation", "--kind", help="observation | decision | learning."),
    link: list[str] = typer.Option(None, "--link", help="Wikilink slug to relate this to (repeatable)."),
) -> None:
    """Persist an observation, decision or learning to episodic memory."""
    _, _, store = _load(root, config=False)
    path = ops.remember(store, " ".join(content), kind=kind, links=list(link or []))
    typer.echo(f"Remembered ({kind}) → {path}")


@app.command()
def active(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    focus: str = typer.Option(..., "--focus", help="What you are working on now."),
    progress: str = typer.Option("", "--progress", help="What is done."),
    open_questions: str = typer.Option("", "--open-questions", help="What is still unresolved."),
) -> None:
    """Update the active working state (current focus, progress, open questions)."""
    _, _, store = _load(root, config=False)
    ops.update_active(store, focus, progress, open_questions)
    typer.echo("Active context updated.")


@app.command()
def handoff(
    summary: list[str] = typer.Argument(..., help="What this session did."),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    decisions: str = typer.Option("", "--decisions", help="Decisions taken."),
    open_questions: str = typer.Option("", "--open-questions", help="Left unresolved."),
    next_steps: str = typer.Option("", "--next-steps", help="What the next session should pick up."),
) -> None:
    """Write a structured end-of-session handoff the next session resumes from."""
    _, _, store = _load(root, config=False)
    path = ops.record_handoff(store, " ".join(summary), decisions, open_questions, next_steps)
    typer.echo(f"Handoff written → {path}")


@app.command()
def bootstrap(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    max_tokens: Optional[int] = typer.Option(None, "--max-tokens", help="Override the budget for this call."),
) -> None:
    """Print the budgeted whole-pyramid digest an agent reads at session start."""
    _, config, store = _load(root)
    typer.echo(ops.bootstrap_session(store, config, max_tokens=max_tokens))


@app.command()
def intent(
    topic: list[str] = typer.Argument(None, help="Optional topic to surface relevant symbols for."),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
) -> None:
    """Surface the architecture (patterns, tech, ADRs) and symbols for a topic."""
    _, config, store = _load(root)
    typer.echo(ops.get_intent(store, config, " ".join(topic) if topic else None))


@app.command()
def decision(
    title: str = typer.Argument(..., help="The decision, as a title."),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    context: str = typer.Option(..., "--context", help="Why this came up."),
    decision_text: str = typer.Option(..., "--decision", help="What was decided."),
    consequences: str = typer.Option("", "--consequences", help="What follows from it."),
    supersedes: Optional[str] = typer.Option(None, "--supersedes", help="ADR id or slug this replaces."),
) -> None:
    """Record an Architecture Decision Record. Add machine-readable `rules:` by
    hand afterwards, or adopt a practice pack — `torsor guard` enforces them."""
    _, _, store = _load(root, config=False)
    path = ops.record_decision(store, title, context, decision_text, consequences,
                               None, supersedes)
    typer.echo(f"Recorded → {path}")
    typer.echo("Add a `rules:` block to make it machine-enforced, then: torsor rules --scoped")


@app.command()
def stats(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    as_json: bool = typer.Option(False, "--json", help="Emit the numbers as JSON."),
) -> None:
    """How big this project's memory is, what gets recalled, whether the map is current."""
    _, config, store = _load(root)
    data = ops.stats(store, config)
    if _emit(data, as_json):
        return
    notes = data["notes"]
    typer.echo(f"notes:    {notes['total']}  (" +
               ", ".join(f"{tier.lower()} {n}" for tier, n in sorted(notes["by_tier"].items())) + ")")
    typer.echo(f"map:      {data['symbols']} symbol(s), {data['modules']} module(s), {data['edges']} edge(s)")
    if data["map_current"] is not None:
        typer.echo(f"          {'current' if data['map_current'] else 'stale — run `torsor map`'}")
    typer.echo(f"index:    {data['index_bytes'] / 1e6:.1f} MB")
    typer.echo(f"embedder: {data['embedder']}")
    if data["top_recalled"]:
        typer.echo("recalled most:")
        for path, count in data["top_recalled"]:
            typer.echo(f"  {count}x  {path}")
    if data["op_totals"]:
        typer.echo("operations: " + ", ".join(f"{op} {n}" for op, n in sorted(data["op_totals"].items())))


@app.command()
def index(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    full: bool = typer.Option(False, help="Rebuild every note's embedding, ignoring the hash cache."),
) -> None:
    """Build or refresh the derived search index."""
    paths, config, store = _load(root)
    conn = db.connect(paths.index_db)
    try:
        stats = reindex(store, conn, get_embedder(config), full=full)
    finally:
        conn.close()
    typer.echo(f"Indexed {stats['indexed']} note(s), deleted {stats['deleted']}, total {stats['total']}.")


@app.command()
def map(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    force: bool = typer.Option(False, "--force", help="Re-scan even if no source file changed."),
) -> None:
    """Generate the repository symbol map under .torsor/map/."""
    paths, config, store = _load(root)
    stats = ops.map_repo(store, config, force=force)
    langs = dict(stats["languages"])
    unavailable = langs.pop("unavailable", {})
    parts = [f"{k} {v}" for k, v in langs.items()]
    parts += [f"{k} {v} — install torsor-helper[languages]" for k, v in unavailable.items()]
    lang_summary = f" · {', '.join(parts)}" if parts else ""
    if stats.get("skipped"):
        typer.echo(
            f"Map up to date ({stats['symbols']} symbol(s), {stats['modules']} module(s)) — nothing changed."
            f"{lang_summary}"
        )
    else:
        typer.echo(
            f"Mapped {stats['symbols']} symbol(s) across {stats['modules']} module(s) "
            f"({stats['edges']} reference edge(s))."
            f"{lang_summary}"
        )


@app.command()
def impact(
    symbol: str = typer.Argument(..., help="Symbol name to trace (e.g. a function/class name)."),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    limit: int = typer.Option(0, "--limit", help="Max callers to list (0 = budgets.max_items)."),
) -> None:
    """Show the blast radius of a symbol — who references it, across files (run `torsor map` first)."""
    paths, config, store = _load(root)
    res = ops.impact(store, config, symbol, limit=limit or None)
    if res["count"] == 0:
        typer.echo(f"No references to {symbol!r} found (is the map current? run `torsor map`).")
        return
    typer.echo(f"{res['count']} reference(s) to {symbol!r}:")
    for c in res["callers"]:
        typer.echo(f"  {render.caller(c)}")
    if res["truncated"]:
        typer.echo(f"  … +{res['truncated']} more (--limit to list them)")


@app.command()
def connect(
    source: str = typer.Argument(..., help="Start symbol (e.g. a function/class name)."),
    target: str = typer.Argument(..., help="Destination symbol to reach."),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    max_hops: int = typer.Option(12, help="Maximum path length to search."),
) -> None:
    """Trace the shortest call-graph path from one symbol to another (run `torsor map` first)."""
    paths, config, store = _load(root)
    res = ops.connect(store, config, source, target, max_hops=max_hops)
    if not res["found"]:
        typer.echo(
            f"No call path from {source!r} to {target!r} "
            f"(directed; is the map current? run `torsor map`)."
        )
        return
    typer.echo(f"{res['hops']} hop(s) from {source!r} to {target!r}:")
    typer.echo("  " + render.call_path(res["path"]))


@app.command()
def find(
    query: str = typer.Argument(..., help="Fuzzy query for files and mapped symbols."),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    mode: str = typer.Option("fuzzy", help="Match mode: fuzzy | literal | regex."),
    limit: int = typer.Option(20, help="Max results."),
    files_only: bool = typer.Option(False, "--files-only", help="Only repo files."),
    symbols_only: bool = typer.Option(False, "--symbols-only", help="Only mapped symbols."),
) -> None:
    """Fuzzy, frecency-ranked search over the repo's files and mapped symbols."""
    paths, config, store = _load(root)
    res = ops.find_targets(
        store, config, query, mode=mode, limit=limit,
        include_files=not symbols_only, include_symbols=not files_only,
    )
    if not res:
        typer.echo(f"No matches for {query!r}.")
        return
    for r in res:
        if r["type"] == "file":
            typer.echo(f"  {render.find_hit(r)}")
        else:
            typer.echo(f"  {render.find_hit(r)}")


@app.command()
def export(root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/.")) -> None:
    """Export the pyramid to a portable llms.txt + a Mermaid module diagram."""
    paths, config, store = _load(root)
    result = ops.export_project(store, config)
    msg = f"Wrote {result['llms_txt']}"
    if result["diagram"]:
        msg += " + module dependency diagram in the repo map"
    typer.echo(msg)


@app.command()
def rules(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    write: Optional[Path] = typer.Option(None, "--write", help="Write/refresh a managed rules block in this file (e.g. AGENTS.md or CLAUDE.md). Idempotent."),
    client: Optional[str] = typer.Option(None, "--client", help=f"Write to a client's conventional instructions file instead of --write ({', '.join(SUPPORTED_CLIENTS)})."),
    scoped: bool = typer.Option(False, "--scoped", help="Claude Code only: write one path-scoped rule file per ADR under .claude/rules/torsor/ (loaded only when a governed file is touched)."),
) -> None:
    """Print a compact agent-rules digest (charter principles + ADR rules) — paste it into AGENTS.md/CLAUDE.md so agents follow the rules without spending tool-call tokens."""
    tp, config, store = _load(root)
    if scoped and (write is not None or client is not None):
        # It used to return early and ignore them, so the user believed a block
        # had been written somewhere it had not.
        typer.echo("--scoped writes one file per ADR into .claude/rules/torsor/; "
                   "it cannot also target --write or --client.", err=True)
        raise typer.Exit(code=2)
    if scoped:
        written = ops.write_scoped_rules(store, config)
        rel = tp.claude_rules_dir.relative_to(tp.root).as_posix()
        typer.echo(f"Wrote {len(written)} path-scoped rule file(s) → {rel}/ (re-run after recording new ADRs)")
        return
    dest = _resolve_block_target(root, write, client)
    if dest is not None:
        target = ops.write_rules_block(store, config, dest)
        typer.echo(f"Wrote rules block → {target} (re-run after recording new ADRs)")
        return
    digest = ops.agent_rules(store, config)
    if not digest:
        typer.echo("No rules to export yet — fill the charter's principles or record ADRs with rules.")
        return
    typer.echo(digest)


@app.command()
def practices(
    language: Optional[str] = typer.Argument(None, help="python · javascript · typescript · go · rust · agent (default: auto-detect from the repo)."),
    apply: bool = typer.Option(False, "--apply", help="Adopt the pack: record an ADR whose rules `torsor guard` enforces."),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
) -> None:
    """List or adopt curated, research-backed best-practice packs (consensus style-guide + linter rules, weighted toward documented AI-coding failure modes)."""
    tp, config, store = _load(root)
    if apply:
        if not language:
            typer.echo("Pass a language to adopt, e.g. `torsor practices python --apply`.", err=True)
            raise typer.Exit(code=1)
        result = ops.adopt_practices(store, config, language)
        typer.echo(result["message"])
        if not result["adopted"]:
            raise typer.Exit(code=1)
        return
    typer.echo(ops.list_practices(store, config, language))


@app.command()
def primer(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    write: Optional[Path] = typer.Option(None, "--write", help="Write/refresh a managed primer block in this file (e.g. AGENTS.md or CLAUDE.md). Idempotent."),
    client: Optional[str] = typer.Option(None, "--client", help="Write to a client's conventional instructions file instead of --write."),
    tokens: int = typer.Option(800, "--tokens", help="Token budget for the primer."),
) -> None:
    """Token-saver: print a budgeted prompt-time project primer (charter + architecture + repo map + token-efficiency habits) — content in the prompt file costs zero discovery tool-calls per session."""
    tp, config, store = _load(root)
    dest = _resolve_block_target(root, write, client)
    if dest is not None:
        target = ops.write_primer_block(store, config, dest, max_tokens=tokens)
        typer.echo(f"Wrote primer block → {target} (re-run after big changes or `torsor map`)")
        return
    typer.echo(ops.project_primer(store, config, max_tokens=tokens))


@app.command()
def guard(
    paths: list[str] = typer.Argument(None, help="Files to check (default: git-changed .py files)."),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    strict: bool = typer.Option(False, help="Exit non-zero if NEW drift fails the threshold (for CI)."),
    severity: Optional[str] = typer.Option(None, "--severity", help="Strict threshold: hint|info|warning|error. Default: fail on any."),
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON findings."),
    update_baseline: bool = typer.Option(False, "--update-baseline", help="Record current violations as the accepted baseline (grandfather existing debt)."),
) -> None:
    """Check changes against declared architectural intent (ADR rules)."""

    _check_severity(severity)
    tp, config, store = _load(root)
    result = ops.guard_run(
        store, config, paths or None,
        update_baseline=update_baseline, strict=strict, severity=severity,
    )
    violations = result["violations"]

    # --json is honoured even when baselining: returning first meant
    # `guard --json --update-baseline` printed nothing at all.
    new_files = {(v.file, v.line, v.message) for v in result["new"]}
    if _emit([{**v.model_dump(), "new": (v.file, v.line, v.message) in new_files}
              for v in violations], as_json):
        if update_baseline:
            return
        if result["failed"]:
            raise typer.Exit(code=1)
        return

    if update_baseline:
        typer.echo(f"Baselined {len(violations)} violation(s) → {tp.baseline_file}")
        return

    if not violations:
        typer.echo("No drift from declared intent detected.")
        return
    for v in violations:
        typer.echo(render.violation(v))
    tail = f" ({result['baselined']} baselined)" if result["baselined"] else ""
    typer.echo(f"\n{len(violations)} drift violation(s){tail}.")
    if result["failed"]:
        raise typer.Exit(code=1)


@app.command()
def deps(
    files: list[str] = typer.Argument(None, help="Files to check (default: git-changed .py files)."),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    strict: bool = typer.Option(False, help="Exit non-zero if any unknown import is found (for CI)."),
) -> None:
    """Flag imports that resolve to no known package — possible hallucinated dependencies (slopsquatting). Offline."""
    tp, config, store = _load(root)
    findings = ops.check_dependencies(store, config, files or None)
    if not findings:
        typer.echo("No unknown imports — every import resolves to a known package.")
        return
    for f in findings:
        typer.echo(f"{render.unknown_import(f)} (possible hallucinated dependency)")
    typer.echo(f"\n{len(findings)} unknown import(s). Verify each exists before installing.")
    if strict:
        raise typer.Exit(code=1)


@app.command()
def verify(
    paths: list[str] = typer.Argument(None, help="Files to check (default: git-changed)."),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    severity: Optional[str] = typer.Option(None, "--severity", help="Guard threshold: hint|info|warning|error."),
    run_tests: bool = typer.Option(False, "--run-tests", help="Also run a recorded `test` command."),
    as_json: bool = typer.Option(False, "--json", help="Emit the machine-readable verdict."),
) -> None:
    """The deterministic verification gate (guard + deps + staleness [+ tests]).
    Exits non-zero on failure — a loop-engineering / CI / Stop-hook completion check."""

    _check_severity(severity)
    tp, config, store = _load(root)
    verdict = ops.verify(store, config, paths or None, severity=severity, run_tests=run_tests)
    if _emit(verdict, as_json):
        raise typer.Exit(code=verdict["exit_code"])
    for c in verdict["checks"]:
        tail = f" ({c['count']})" if c["count"] else ""
        typer.echo(f"{c['name']}: {c['status'].upper()}{tail}")
        for reason in c["reasons"]:
            typer.echo(f"  - {reason}")
        hidden = c["count"] - len(c["reasons"])
        if hidden > 0:
            typer.echo(f"  … +{hidden} more")
    typer.echo(f"\n{'PASS' if verdict['ok'] else 'FAIL'}")
    raise typer.Exit(code=verdict["exit_code"])


@app.command()
def stale(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    mark: bool = typer.Option(False, "--mark", help="Set status: stale on notes with findings (reversible)."),
    unmark: bool = typer.Option(False, "--unmark", help="Restore status: active on all stale-marked notes."),
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON findings."),
    strict: bool = typer.Option(False, help="Exit non-zero if any staleness finding (for CI)."),
) -> None:
    """Flag memory that contradicts current code: dangling [[wikilinks]] and dead
    file-path references. Read-only unless --mark/--unmark. Deterministic, offline."""

    tp, config, store = _load(root)
    if mark and unmark:
        typer.echo("--mark and --unmark are opposites; pass one.", err=True)
        raise typer.Exit(code=2)
    result = ops.check_staleness(store, config, mark=mark, unmark=unmark)
    findings = result["findings"]

    if _emit([r.model_dump() for r in findings], as_json):
        pass
    elif not findings:
        typer.echo("No staleness detected — memory matches the code.")
    else:
        for r in findings:
            typer.echo(f"[{r.kind}] {r.message}")
        typer.echo(f"\n{len(findings)} staleness finding(s).")
    if result["marked"]:
        verb = "Unmarked" if unmark else "Marked"
        typer.echo(f"{verb} {len(result['marked'])} note(s).")
    if strict and findings:
        raise typer.Exit(code=1)


@app.command()
def coach(
    context: list[str] = typer.Argument(None, help="Optional context for best-practice hints (e.g. what you're building)."),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    dismiss: str = typer.Option(None, help="Dismiss a recommendation by its key."),
) -> None:
    """Show health + best-practice recommendations (the Coach). Advisory; never blocks."""
    tp, config, store = _load(root)
    if dismiss:
        ops.dismiss_recommendation(store, dismiss)
        typer.echo(f"Dismissed {dismiss}.")
        return
    recs = ops.recommend(store, config, " ".join(context) if context else None)
    if not recs:
        typer.echo("No recommendations right now — the project looks healthy.")
        return
    for r in recs:
        typer.echo(render.recommendation(r, arrow="->"))


@app.command()
def clean(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    apply: bool = typer.Option(False, "--apply", help="Actually delete (default is a dry run)."),
    deep: bool = typer.Option(False, "--deep", help="Also drop the whole disposable index."),
    yes: bool = typer.Option(False, "--yes", help="Confirm a destructive --apply --deep."),
) -> None:
    """Reclaim orphaned map notes, dead index rows and expired journals. Dry run by default."""
    if apply and deep and not yes:
        typer.echo(
            "--apply --deep removes the entire .torsor/.index/ directory. Most of it rebuilds "
            "from Markdown, but the learned frecency and op-frequency data do not. Re-run with "
            "--yes to confirm.",
            err=True,
        )
        raise typer.Exit(code=2)
    tp, config, store = _load(root)
    stats = ops.clean(store, config, apply=apply, deep=deep)

    for note in stats["notes"]:
        typer.echo(note)
    verb = "Removed" if apply else "Would remove"
    typer.echo(
        f"{verb} {stats['map_orphans']} orphaned map note(s), "
        f"{stats['journals_expired']} expired journal(s), "
        f"{stats['dead_rows']} dead index row(s)"
        + (" and the whole index" if stats["deep"] else "")
        + f" — {_human_bytes(stats['reclaimed_bytes'])}."
    )
    if stats["files"]:
        for rel in stats["files"]:
            typer.echo(f"  {rel}")
    if stats["dry_run"]:
        if stats["files"] or stats["dead_rows"]:
            typer.echo("Nothing was deleted. Re-run with --apply to act on this plan.")
        else:
            typer.echo("Nothing to reclaim. (Re-run with --apply once there is.)")
    elif stats["insights_mined"]:
        typer.echo(f"Mined {stats['insights_mined']} insight file(s) before expiring journals.")


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} B"


@app.command()
def consolidate(root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/.")) -> None:
    """Self-improving maintenance: mine journal insights, reindex, report duplicates."""
    tp, config, store = _load(root)
    stats = ops.consolidate(store, config)
    typer.echo(
        f"Mined {stats['insights']} insight file(s); reindexed {stats['indexed']} note(s); "
        f"found {stats['duplicates']} duplicate entr(y/ies)."
    )
    for text, n in stats["duplicate_entries"][:5]:
        # "found 7 duplicates" with no way to see them was a dead end.
        typer.echo(f"  {n}x  {text[:80]}")
    if stats["top_accessed"]:
        hot = ", ".join(f"{path} ({n}x)" for path, n in stats["top_accessed"])
        typer.echo(f"Most-recalled: {hot}")


@app.command()
def recipes(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    limit: int = typer.Option(10, help="Max recipes to show."),
) -> None:
    """Show the deterministic torsor lookups you run most — prime candidates to route to the cheap model."""
    tp, _, store = _load(root, config=False)
    recs = ops.recipes(store, limit)
    if not recs:
        typer.echo("No recorded operations yet — use torsor for a while, then check back.")
        return
    typer.echo("Most-repeated torsor lookups (route these to the cheap model — see `torsor models`):")
    for r in recs:
        arg = f" {r['args']!r}" if r["args"] else ""
        typer.echo(f"  {r['hits']}×  {r['op']}{arg}")


@app.command()
def commands(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    add: Optional[tuple[str, str]] = typer.Option(
        (None, None), "--add", help="Record a command: --add NAME COMMAND (e.g. --add test 'uv run pytest').",
        metavar="NAME COMMAND",
    ),
    note: str = typer.Option("", help="Optional description for --add."),
    run: Optional[str] = typer.Option(None, "--run", help="Run a recorded command by name."),
) -> None:
    """Record & replay the project's commands so agents don't re-derive them each session."""
    tp, _, store = _load(root, config=False)
    name, command = add if add else (None, None)
    if name:
        # Two arguments, not 'name=command': the ad-hoc split broke any command
        # containing "=" (`FOO=bar pytest`), which is a normal thing to record.
        ops.record_command(store, name.strip(), command.strip(), note)
        typer.echo(f"Recorded command {name.strip()!r}.")
        return
    if run is not None:
        result = ops.run_command(store, run)
        if result is None:
            typer.echo(f"No command named {run!r}. See: torsor commands", err=True)
            raise typer.Exit(code=1)
        raise typer.Exit(code=result.returncode)
    cmds = ops.list_commands(store)
    if not cmds:
        typer.echo("No commands recorded yet. Add one:  torsor commands --add test 'uv run pytest'")
        return
    for c in cmds:
        typer.echo(f"  {render.command(c)}")


@app.command()
def models(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    cheap: Optional[str] = typer.Option(None, help="Model id for basic, deterministic work (torsor lookups, command replays)."),
    smart: Optional[str] = typer.Option(None, help="Model id for thinking & construction (design, code, decisions)."),
    fast: Optional[str] = typer.Option(None, help="Optional mid-tier model id."),
    write: Optional[Path] = typer.Option(None, "--write", help="Merge the Markdown policy block into an instructions file (AGENTS.md, CLAUDE.md, …). Existing content is preserved."),
    write_json: Optional[Path] = typer.Option(None, "--write-json", help="Write the machine-readable policy to a JSON file. Replaces the file."),
    client: Optional[str] = typer.Option(None, "--client", help="Write the Markdown policy to a client's conventional instructions file instead of --write."),
    json_out: bool = typer.Option(False, "--json", help="Print the machine-readable policy (for piping into any harness's router)."),
) -> None:
    """Set cheap/smart model tiers and publish the routing policy (token thrift). App-agnostic: any MCP client, any agent rules file, or any programmatic router can consume it."""
    import json as _json

    tp, config, store = _load(root)
    if cheap is not None or smart is not None or fast is not None:
        if cheap is not None:
            config.models.cheap = cheap
        if smart is not None:
            config.models.smart = smart
        if fast is not None:
            config.models.fast = fast
        save_config(tp, config)
        typer.echo("Updated [models] in torsor.toml.")
    if write is not None and str(write).endswith(".json"):
        # One flag used to mean two things: a .md target got a merged block, a
        # .json target had its whole content replaced. Silent data loss if you
        # aimed it at a config file you already had.
        typer.echo("--write merges a Markdown block; use --write-json for a JSON policy file.", err=True)
        raise typer.Exit(code=2)
    if write_json is not None:
        # Relative to the project root, like --write — not the shell's cwd.
        target = write_json if write_json.is_absolute() else root / write_json
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_json.dumps(ops.model_policy_json(store, config), indent=2) + "\n",
                          encoding="utf-8")
        typer.echo(f"Wrote machine-readable model policy to {target} (for programmatic routers).")
        return
    dest = _resolve_block_target(root, write, client)
    if dest is not None:
        ops.write_model_policy(store, config, dest)
        typer.echo(f"Wrote Model-routing block to {dest} (any agent that reads this file follows it).")
        return
    if json_out:
        typer.echo(_json.dumps(ops.model_policy_json(store, config), indent=2))
        return
    typer.echo(f"cheap: {config.models.cheap or '(unset)'}")
    typer.echo(f"smart: {config.models.smart or '(unset)'}")
    if config.models.fast:
        typer.echo(f"fast:  {config.models.fast}")
    typer.echo("\n" + ops.model_policy(store, config))


hooks_app = typer.Typer(help="Auto-capture: wire memory to the git / Claude Code lifecycle.")
app.add_typer(hooks_app, name="hooks")


@hooks_app.command("install")
def hooks_install(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    no_git: bool = typer.Option(False, "--no-git", help="Skip git hooks."),
    no_claude: bool = typer.Option(False, "--no-claude", help="Skip Claude Code settings."),
    local: bool = typer.Option(False, "--local", help="Write .claude/settings.local.json (git-ignored) instead."),
    on_stop: bool = typer.Option(False, "--on-stop", help="Register the Stop event instead of SessionEnd."),
) -> None:
    """Install auto-capture hooks (project digest on session start + after compaction,
    ADR drift check on every proposed edit, auto-handoff on session end, auto-map on commit). Idempotent and removable; never
    clobbers your existing hooks or settings."""
    _, config, store = _load(root)
    result = ops.install_hooks(store, config, git=not no_git, claude=not no_claude, local=local, on_stop=on_stop)
    for h in result["git_hooks"]:
        typer.echo(f"git hook: {h}")
    if result["claude_settings"]:
        typer.echo(f"claude settings: {result['claude_settings']}")
    for w in result["warnings"]:
        typer.echo(f"warning: {w}", err=True)


@hooks_app.command("uninstall")
def hooks_uninstall(
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
    local: bool = typer.Option(False, "--local", help="Accepted for compatibility; both settings files are always cleaned."),
) -> None:
    """Remove only torsor-owned git hooks and Claude Code hook entries.
    Cleans settings.json and settings.local.json both, so nothing is left firing."""
    _, config, store = _load(root)
    result = ops.uninstall_hooks(store, config, local=local)
    for h in result["removed"]:
        typer.echo(f"removed: {h}")
    for path in result["cleaned"]:
        typer.echo(f"cleaned: {path}")
    for w in result["warnings"]:
        typer.echo(f"warning: {w}", err=True)
    if not result["removed"] and not result["cleaned"]:
        typer.echo("Nothing to uninstall.")


@hooks_app.command("status")
def hooks_status_cmd(root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/.")) -> None:
    """Show which git hooks and Claude Code events currently carry a torsor entry."""
    _, config, store = _load(root)
    status = ops.hooks_status(store, config)
    if not status["git_repo"]:
        typer.echo("git: not a repo here")
    else:
        for name, on in status["git_hooks"].items():
            typer.echo(f"git {name}: {'installed' if on else 'not installed'}")
    events = status["claude_events"]
    typer.echo(f"claude events: {', '.join(events) if events else 'none'}")


@hooks_app.command("run")
def hooks_run(
    event: str = typer.Argument(..., help="post-commit | pre-push | pre-edit | session-start | session-end"),
    root: Path = typer.Option(Path("."), "--root", "-r", envvar="TORSOR_ROOT", help="Project root containing .torsor/."),
) -> None:
    """Stable dispatcher the on-disk hook scripts call — so scripts never change
    across upgrades. Best-effort; a missing project just exits 0."""
    tp = TorsorPaths(root)
    if not tp.base.exists():
        return  # nothing to capture; never break the git/agent lifecycle
    config = load_config(tp)
    store = Store(tp)
    if event == "post-commit":
        ops.on_commit(store, config)
    elif event == "session-start":
        import json

        payload = _hook_payload()
        text = ops.session_start_context(store, config, how=payload.get("how_session_started") or "startup")
        if text:
            # Claude Code's context-injection contract for SessionStart.
            typer.echo(json.dumps({
                "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text},
            }))
    elif event == "pre-edit":
        import json

        payload = _hook_payload()
        verdict = ops.pre_edit(store, config, payload.get("tool_name"), payload.get("tool_input"))
        if verdict:
            out = {"hookEventName": "PreToolUse", "additionalContext": verdict["context"]}
            if verdict["decision"] == "deny":
                out["permissionDecision"] = "deny"
                out["permissionDecisionReason"] = verdict["context"]
            typer.echo(json.dumps({"hookSpecificOutput": out}))
    elif event == "session-end":
        payload = _hook_payload()
        ops.auto_handoff(
            store, config,
            session_id=payload.get("session_id"), transcript_path=payload.get("transcript_path"),
        )
    elif event == "pre-push":
        result = ops.pre_push(store, config)
        if result["failed"]:
            for v in result["new"]:
                typer.echo(f"{v.file}:{v.line} — [{v.severity}] {v.message} (per {v.source})", err=True)
            raise typer.Exit(code=1)
    else:
        typer.echo(f"unknown hook event {event!r}", err=True)
        raise typer.Exit(code=2)


def _hook_payload() -> dict:
    """The JSON Claude Code pipes to a hook on stdin; {} when absent or malformed
    (a hook must never fail the agent lifecycle over its own input)."""
    import json
    import sys

    if sys.stdin.isatty():
        return {}
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def main() -> None:
    app()
