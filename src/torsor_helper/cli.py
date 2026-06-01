from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from torsor_helper.clients import SUPPORTED_CLIENTS, config_snippet
from torsor_helper.config import TorsorConfig, load_config, save_config
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
def mcp(root: Path = typer.Option(Path("."), help="Project root containing .torsor/.")) -> None:
    """Run the torsor-helper MCP server over stdio."""
    from torsor_helper.server import run

    run(root)


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


def main() -> None:
    app()
