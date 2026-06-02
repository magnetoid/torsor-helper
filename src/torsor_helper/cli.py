from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from torsor_helper import db
from torsor_helper import operations as ops
from torsor_helper.clients import SUPPORTED_CLIENTS, config_snippet
from torsor_helper.config import TorsorConfig, load_config, save_config
from torsor_helper.embeddings import get_embedder
from torsor_helper.indexer import reindex
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

app = typer.Typer(help="torsor-helper: persistent memory + architectural intent over MCP.")


@app.command()
def init(
    root: Path = typer.Option(Path("."), help="Project root to scaffold .torsor/ in."),
    client: Optional[str] = typer.Option(None, help=f"Print MCP config for: {', '.join(SUPPORTED_CLIENTS)}"),
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
    if client:
        typer.echo(f"\n# MCP config for {SUPPORTED_CLIENTS[client]}:\n")
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

    run(root, transport="streamable-http" if http else "stdio", host=host, port=port)


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
def map(root: Path = typer.Option(Path("."), help="Project root to map.")) -> None:
    """Generate the repository symbol map under .torsor/map/."""
    paths = TorsorPaths(root)
    if not paths.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(paths)
    store = Store(paths)
    stats = ops.map_repo(store, config)
    typer.echo(f"Mapped {stats['symbols']} symbol(s) across {stats['modules']} module(s).")


@app.command()
def guard(
    paths: list[str] = typer.Argument(None, help="Files to check (default: git-changed .py files)."),
    root: Path = typer.Option(Path("."), help="Project root."),
    strict: bool = typer.Option(False, help="Exit non-zero if any violation is found (for CI)."),
) -> None:
    """Check changes against declared architectural intent (ADR rules)."""
    tp = TorsorPaths(root)
    if not tp.base.exists():
        typer.echo("torsor-helper not initialized here (run `torsor init`).", err=True)
        raise typer.Exit(code=1)
    config = load_config(tp)
    store = Store(tp)
    violations = ops.check_drift(store, config, paths or None)
    if not violations:
        typer.echo("No drift from declared intent detected.")
        return
    for v in violations:
        typer.echo(f"{v.file}:{v.line} — {v.message} (per {v.source})")
    typer.echo(f"\n{len(violations)} drift violation(s).")
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


def main() -> None:
    app()
