from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from torsor_helper import db
from torsor_helper import operations as ops
from torsor_helper.clients import SUPPORTED_CLIENTS, config_location, config_snippet
from torsor_helper.config import TorsorConfig, load_config, save_config
from torsor_helper.embeddings import get_embedder
from torsor_helper.indexer import reindex
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

app = typer.Typer(help="torsor-helper: persistent memory + architectural intent over MCP.")


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


@app.command()
def init(
    root: Path = typer.Option(Path("."), help="Project root to scaffold .torsor/ in."),
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


@app.command()
def mcp(
    root: Path = typer.Option(Path("."), help="Project root containing .torsor/."),
    http: bool = typer.Option(False, "--http", help="Serve over HTTP (streamable-http) instead of stdio — for shared/remote/team use."),
    host: str = typer.Option("127.0.0.1", help="Host to bind when --http."),
    port: int = typer.Option(8000, help="Port to bind when --http."),
) -> None:
    """Run the torsor-helper MCP server (stdio by default; --http for a shared service)."""
    from torsor_helper.server import run

    if http and host not in ("127.0.0.1", "localhost", "::1"):
        typer.echo(
            "WARNING: the HTTP transport has no authentication. Binding to a non-loopback "
            f"host ({host}) exposes read/write access to this project's memory to anyone who "
            "can reach the port. Put it behind a reverse proxy with auth, or use an SSH tunnel.",
            err=True,
        )
    run(root, transport="streamable-http" if http else "stdio", host=host, port=port)


@app.command()
def update(
    print_only: bool = typer.Option(False, "--print-only", help="Show the upgrade command without running it."),
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
    result = subprocess.run(cmd)
    if result.returncode != 0:
        typer.echo("Update failed — run the command above manually.", err=True)
        raise typer.Exit(code=result.returncode)
    typer.echo("Updated. Check with: torsor --version")


@app.command()
def doctor(root: Path = typer.Option(Path("."), help="Project root to check.")) -> None:
    """Verify a torsor-helper project is healthy."""
    paths = TorsorPaths(root)
    if not paths.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    missing = [
        p.name
        for p in (paths.charter, paths.system_patterns, paths.active_context, paths.progress)
        if not p.exists()
    ]
    if missing:
        typer.echo(f"Project incomplete; missing: {', '.join(missing)}", err=True)
        raise typer.Exit(code=1)
    try:
        load_config(paths)
    except Exception as exc:  # malformed TOML or invalid schema
        typer.echo(f"Config malformed: {exc}", err=True)
        raise typer.Exit(code=1)
    typer.echo("OK: torsor-helper project is healthy.")


@app.command()
def index(
    root: Path = typer.Option(Path("."), help="Project root containing .torsor/."),
    full: bool = typer.Option(False, help="Rebuild every note's embedding, ignoring the hash cache."),
) -> None:
    """Build or refresh the derived search index."""
    paths = TorsorPaths(root)
    if not paths.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(paths)
    store = Store(paths)
    conn = db.connect(paths.index_db)
    try:
        stats = reindex(store, conn, get_embedder(config), full=full)
    finally:
        conn.close()
    typer.echo(f"Indexed {stats['indexed']} note(s), deleted {stats['deleted']}, total {stats['total']}.")


@app.command()
def map(
    root: Path = typer.Option(Path("."), help="Project root to map."),
    force: bool = typer.Option(False, "--force", help="Re-scan even if no source file changed."),
) -> None:
    """Generate the repository symbol map under .torsor/map/."""
    paths = TorsorPaths(root)
    if not paths.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(paths)
    store = Store(paths)
    stats = ops.map_repo(store, config, force=force)
    if stats.get("skipped"):
        typer.echo(f"Map up to date ({stats['symbols']} symbol(s), {stats['modules']} module(s)) — nothing changed.")
    else:
        typer.echo(
            f"Mapped {stats['symbols']} symbol(s) across {stats['modules']} module(s) "
            f"({stats['edges']} reference edge(s))."
        )


@app.command()
def impact(
    symbol: str = typer.Argument(..., help="Symbol name to trace (e.g. a function/class name)."),
    root: Path = typer.Option(Path("."), help="Project root."),
) -> None:
    """Show the blast radius of a symbol — who references it, across files (run `torsor map` first)."""
    paths = TorsorPaths(root)
    if not paths.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(paths)
    store = Store(paths)
    res = ops.impact(store, config, symbol)
    if res["count"] == 0:
        typer.echo(f"No references to {symbol!r} found (is the map current? run `torsor map`).")
        return
    typer.echo(f"{res['count']} reference(s) to {symbol!r}:")
    for c in res["callers"]:
        typer.echo(f"  {c['module']} :: {c['caller']}")


@app.command()
def find(
    query: str = typer.Argument(..., help="Fuzzy query for files and mapped symbols."),
    root: Path = typer.Option(Path("."), help="Project root."),
    mode: str = typer.Option("fuzzy", help="Match mode: fuzzy | literal | regex."),
    limit: int = typer.Option(20, help="Max results."),
    files_only: bool = typer.Option(False, "--files-only", help="Only repo files."),
    symbols_only: bool = typer.Option(False, "--symbols-only", help="Only mapped symbols."),
) -> None:
    """Fuzzy, frecency-ranked search over the repo's files and mapped symbols."""
    paths = TorsorPaths(root)
    if not paths.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(paths)
    store = Store(paths)
    res = ops.find_targets(
        store, config, query, mode=mode, limit=limit,
        include_files=not symbols_only, include_symbols=not files_only,
    )
    if not res:
        typer.echo(f"No matches for {query!r}.")
        return
    for r in res:
        if r["type"] == "file":
            typer.echo(f"  {r['path']}")
        else:
            typer.echo(f"  {r['module']}:{r['line']}  {r['name']} ({r['kind']})")


@app.command()
def export(root: Path = typer.Option(Path("."), help="Project root to export.")) -> None:
    """Export the pyramid to a portable llms.txt + a Mermaid module diagram."""
    paths = TorsorPaths(root)
    if not paths.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(paths)
    store = Store(paths)
    result = ops.export_project(store, config)
    msg = f"Wrote {result['llms_txt']}"
    if result["diagram"]:
        msg += " + module dependency diagram in the repo map"
    typer.echo(msg)


@app.command()
def rules(
    root: Path = typer.Option(Path("."), help="Project root."),
    write: Optional[Path] = typer.Option(None, "--write", help="Write/refresh a managed rules block in this file (e.g. AGENTS.md or CLAUDE.md). Idempotent."),
) -> None:
    """Print a compact agent-rules digest (charter principles + ADR rules) — paste it into AGENTS.md/CLAUDE.md so agents follow the rules without spending tool-call tokens."""
    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(tp)
    store = Store(tp)
    if write is not None:
        target = ops.write_rules_block(store, config, write)
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
    root: Path = typer.Option(Path("."), help="Project root."),
) -> None:
    """List or adopt curated, research-backed best-practice packs (consensus style-guide + linter rules, weighted toward documented AI-coding failure modes)."""
    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(tp)
    store = Store(tp)
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
    root: Path = typer.Option(Path("."), help="Project root."),
    write: Optional[Path] = typer.Option(None, "--write", help="Write/refresh a managed primer block in this file (e.g. AGENTS.md or CLAUDE.md). Idempotent."),
    tokens: int = typer.Option(800, "--tokens", help="Token budget for the primer."),
) -> None:
    """Token-saver: print a budgeted prompt-time project primer (charter + architecture + repo map + token-efficiency habits) — content in the prompt file costs zero discovery tool-calls per session."""
    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(tp)
    store = Store(tp)
    if write is not None:
        target = ops.write_primer_block(store, config, write, max_tokens=tokens)
        typer.echo(f"Wrote primer block → {target} (re-run after big changes or `torsor map`)")
        return
    typer.echo(ops.project_primer(store, config, max_tokens=tokens))


@app.command()
def guard(
    paths: list[str] = typer.Argument(None, help="Files to check (default: git-changed .py files)."),
    root: Path = typer.Option(Path("."), help="Project root."),
    strict: bool = typer.Option(False, help="Exit non-zero if NEW drift fails the threshold (for CI)."),
    severity: Optional[str] = typer.Option(None, "--severity", help="Strict threshold: hint|info|warning|error. Default: fail on any."),
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON findings."),
    update_baseline: bool = typer.Option(False, "--update-baseline", help="Record current violations as the accepted baseline (grandfather existing debt)."),
) -> None:
    """Check changes against declared architectural intent (ADR rules)."""
    import json

    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(tp)
    store = Store(tp)
    result = ops.guard_run(
        store, config, paths or None,
        update_baseline=update_baseline, strict=strict, severity=severity,
    )
    violations = result["violations"]

    if update_baseline:
        typer.echo(f"Baselined {len(violations)} violation(s) → {tp.baseline_file}")
        return

    if as_json:
        typer.echo(json.dumps([v.model_dump() for v in violations]))
        if result["failed"]:
            raise typer.Exit(code=1)
        return

    if not violations:
        typer.echo("No drift from declared intent detected.")
        return
    for v in violations:
        typer.echo(f"{v.file}:{v.line} — [{v.severity}] {v.message} (per {v.source})")
    tail = f" ({result['baselined']} baselined)" if result["baselined"] else ""
    typer.echo(f"\n{len(violations)} drift violation(s){tail}.")
    if result["failed"]:
        raise typer.Exit(code=1)


@app.command()
def deps(
    files: list[str] = typer.Argument(None, help="Files to check (default: git-changed .py files)."),
    root: Path = typer.Option(Path("."), help="Project root."),
    strict: bool = typer.Option(False, help="Exit non-zero if any unknown import is found (for CI)."),
) -> None:
    """Flag imports that resolve to no known package — possible hallucinated dependencies (slopsquatting). Offline."""
    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(tp)
    store = Store(tp)
    findings = ops.check_dependencies(store, config, files or None)
    if not findings:
        typer.echo("No unknown imports — every import resolves to a known package.")
        return
    for f in findings:
        typer.echo(f"{f['file']}:{f['line']} — unknown import '{f['name']}' (possible hallucinated dependency)")
    typer.echo(f"\n{len(findings)} unknown import(s). Verify each exists before installing.")
    if strict:
        raise typer.Exit(code=1)


@app.command()
def coach(
    context: list[str] = typer.Argument(None, help="Optional context for best-practice hints (e.g. what you're building)."),
    root: Path = typer.Option(Path("."), help="Project root."),
    dismiss: str = typer.Option(None, help="Dismiss a recommendation by its key."),
) -> None:
    """Show health + best-practice recommendations (the Coach). Advisory; never blocks."""
    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(tp)
    store = Store(tp)
    if dismiss:
        ops.dismiss_recommendation(store, dismiss)
        typer.echo(f"Dismissed {dismiss}.")
        return
    recs = ops.recommend(store, config, " ".join(context) if context else None)
    if not recs:
        typer.echo("No recommendations right now — the project looks healthy.")
        return
    for r in recs:
        tail = f" -> {r.action}" if r.action else ""
        typer.echo(f"[{r.severity}/{r.kind}] {r.message}{tail}  (key: {r.key})")


@app.command()
def consolidate(root: Path = typer.Option(Path("."), help="Project root.")) -> None:
    """Self-improving maintenance: mine journal insights, reindex, report duplicates."""
    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(tp)
    store = Store(tp)
    stats = ops.consolidate(store, config)
    typer.echo(
        f"Mined {stats['insights']} insight file(s); reindexed {stats['indexed']} note(s); "
        f"found {stats['duplicates']} duplicate entr(y/ies)."
    )
    if stats["top_accessed"]:
        hot = ", ".join(f"{path} ({n}x)" for path, n in stats["top_accessed"])
        typer.echo(f"Most-recalled: {hot}")


@app.command()
def recipes(
    root: Path = typer.Option(Path("."), help="Project root."),
    limit: int = typer.Option(10, help="Max recipes to show."),
) -> None:
    """Show the deterministic torsor lookups you run most — prime candidates to route to the cheap model."""
    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    store = Store(tp)
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
    root: Path = typer.Option(Path("."), help="Project root."),
    add: Optional[str] = typer.Option(None, "--add", help="Record a command as 'name=command' (e.g. --add 'test=uv run pytest')."),
    note: str = typer.Option("", help="Optional description for --add."),
    run: Optional[str] = typer.Option(None, "--run", help="Run a recorded command by name."),
) -> None:
    """Record & replay the project's commands so agents don't re-derive them each session."""
    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    store = Store(tp)
    if add is not None:
        if "=" not in add:
            typer.echo("Use --add 'name=command' (e.g. 'test=uv run pytest').", err=True)
            raise typer.Exit(code=1)
        name, _, command = add.partition("=")
        ops.record_command(store, name.strip(), command.strip(), note)
        typer.echo(f"Recorded command '{name.strip()}'.")
        return
    if run is not None:
        result = ops.run_command(store, run)
        if result is None:
            typer.echo(f"No command named {run!r}. See: torsor commands", err=True)
            raise typer.Exit(code=1)
        raise typer.Exit(code=result.returncode)
    cmds = ops.list_commands(store)
    if not cmds:
        typer.echo("No commands recorded yet. Add one:  torsor commands --add 'test=uv run pytest'")
        return
    for c in cmds:
        tail = f"  — {c['note']}" if c["note"] else ""
        typer.echo(f"  {c['name']}: {c['command']}{tail}")


@app.command()
def models(
    root: Path = typer.Option(Path("."), help="Project root."),
    cheap: Optional[str] = typer.Option(None, help="Model id for basic, deterministic work (torsor lookups, command replays)."),
    smart: Optional[str] = typer.Option(None, help="Model id for thinking & construction (design, code, decisions)."),
    fast: Optional[str] = typer.Option(None, help="Optional mid-tier model id."),
    write: Optional[Path] = typer.Option(None, "--write", help="Publish the policy to a file: a *.md/AGENTS.md/CLAUDE.md target gets a Markdown block (any agent reads it); a *.json target gets machine-readable JSON (any router reads it)."),
    json_out: bool = typer.Option(False, "--json", help="Print the machine-readable policy (for piping into any harness's router)."),
) -> None:
    """Set cheap/smart model tiers and publish the routing policy (token thrift). App-agnostic: any MCP client, any agent rules file, or any programmatic router can consume it."""
    import json as _json

    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(tp)
    store = Store(tp)
    if cheap is not None or smart is not None or fast is not None:
        if cheap is not None:
            config.models.cheap = cheap
        if smart is not None:
            config.models.smart = smart
        if fast is not None:
            config.models.fast = fast
        save_config(tp, config)
        typer.echo("Updated [models] in torsor.toml.")
    if write is not None:
        target = write if write.is_absolute() else root / write
        if str(target).endswith(".json"):
            target.write_text(_json.dumps(ops.model_policy_json(store, config), indent=2) + "\n", encoding="utf-8")
            typer.echo(f"Wrote machine-readable model policy to {target} (for programmatic routers).")
        else:
            ops.write_model_policy(store, config, target)
            typer.echo(f"Wrote Model-routing block to {target} (any agent that reads this file follows it).")
        return
    if json_out:
        typer.echo(_json.dumps(ops.model_policy_json(store, config), indent=2))
        return
    typer.echo(f"cheap: {config.models.cheap or '(unset)'}")
    typer.echo(f"smart: {config.models.smart or '(unset)'}")
    if config.models.fast:
        typer.echo(f"fast:  {config.models.fast}")
    typer.echo("\n" + ops.model_policy(store, config))


def main() -> None:
    app()
