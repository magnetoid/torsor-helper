"""Every command and tool must appear in the docs people read.

The README's two reference tables and docs/how-to-use.md were maintained by
hand, so `connect`, `verify`, `stale`, `clean`, the whole `hooks` sub-app and
ten MCP tools were simply missing — everything shipped after v0.4. The repo
already had this pattern for clients (test_clients.py) and never pointed it at
its own surface.
"""
from __future__ import annotations

import ast
from pathlib import Path

import anyio
import pytest

from torsor_helper.paths import TorsorPaths
from torsor_helper.server import build_server
from torsor_helper.store import Store

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
HOW_TO_USE = (ROOT / "docs" / "how-to-use.md").read_text(encoding="utf-8")


def _sub_apps(tree) -> dict[str, str]:
    """{typer variable name: the word a user types}, read off add_typer calls —
    so a new sub-app is prefixed correctly without editing this test. Hardcoding
    "hooks " here meant `torsor merge status` was checked as bare "status",
    which the README happened to contain, and the check passed for nothing."""
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_typer"
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            name = next((k.value.value for k in node.keywords if k.arg == "name"), None)
            if name:
                out[node.args[0].id] = name
    return out


def _cli_commands() -> set[str]:
    """Every invocable command, spelled the way a user types it — so the hooks
    sub-app contributes "hooks install", not "install".

    Hidden commands are excluded: `merge driver` is a git merge driver, invoked
    by git with git's own arguments, and documenting it as something to type
    would be wrong rather than merely redundant."""
    tree = ast.parse((ROOT / "src" / "torsor_helper" / "cli.py").read_text(encoding="utf-8"))
    sub_apps = _sub_apps(tree)
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            text = ast.unparse(dec)
            if ".command" not in text:
                continue
            if any(k.arg == "hidden" and k.value.value for k in getattr(dec, "keywords", [])):
                continue
            explicit = [a for a in getattr(dec, "args", []) if isinstance(a, ast.Constant)]
            name = explicit[0].value if explicit else node.name
            owner = text.split(".command")[0]
            prefix = f"{sub_apps[owner]} " if owner in sub_apps else ""
            names.add(prefix + name)
    return names


def _mcp_tools(tmp_path) -> set[str]:
    Store(TorsorPaths(tmp_path)).scaffold()
    return {t.name for t in anyio.run(build_server(tmp_path).list_tools)}


@pytest.mark.parametrize("command", sorted(_cli_commands()))
def test_every_cli_command_is_documented(command):
    assert f"torsor {command}" in README or f"torsor {command}" in HOW_TO_USE, (
        f"`torsor {command}` appears in neither README.md nor docs/how-to-use.md"
    )


def test_every_mcp_tool_is_documented(tmp_path):
    undocumented = sorted(
        name for name in _mcp_tools(tmp_path)
        if name not in README and name not in HOW_TO_USE
    )
    assert not undocumented, f"MCP tools missing from the docs: {undocumented}"


def test_the_badges_match_reality():
    import re

    from torsor_helper import __version__

    badge = re.search(r"badge/release-v([\d.]+)", README)
    assert badge, "no release badge in README.md"
    assert __version__.startswith(badge.group(1)), (
        f"README badge says v{badge.group(1)}, package says {__version__}"
    )
