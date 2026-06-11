"""Self-update for the torsor CLI.

Detects how the running `torsor` was installed (uv tool, pipx, pip, or a dev
checkout) and produces the right upgrade command. CLI-only by design: an MCP
server should not replace its own code mid-session, so there is deliberately
no MCP tool for this.
"""
from __future__ import annotations

import sys
from pathlib import Path

PYPI_NAME = "torsor-helper"
REPO_URL = "git+https://github.com/magnetoid/torsor-helper"


def detect_install_method() -> str:
    """Best-effort detection from the running interpreter / package location:
    'uv-tool' | 'pipx' | 'dev' | 'pip' (pip is the fallback)."""
    exe = Path(sys.executable).resolve().as_posix()
    if "/pipx/" in exe:
        return "pipx"
    if "/uv/tools/" in exe or "/uv/python" in exe and "/tools/" in exe:
        return "uv-tool"
    try:
        import torsor_helper

        pkg = Path(torsor_helper.__file__).resolve()
        # src layout checkout: .../<repo>/src/torsor_helper/__init__.py
        repo = pkg.parents[2]
        if (repo / "pyproject.toml").exists() and (repo / ".git").exists():
            return "dev"
    except Exception:
        pass
    return "pip"


def update_command(method: str) -> list[str] | None:
    """The upgrade command for an install method, or None when updating is the
    user's job (dev checkout / unknown)."""
    if method == "uv-tool":
        # `uv tool upgrade` re-resolves the original requirement — including
        # git installs, where it fetches the latest commit.
        return ["uv", "tool", "upgrade", PYPI_NAME]
    if method == "pipx":
        return ["pipx", "upgrade", PYPI_NAME]
    if method == "pip":
        return [sys.executable, "-m", "pip", "install", "--upgrade", PYPI_NAME]
    return None


def manual_hint(method: str) -> str:
    if method == "dev":
        return "Running from a source checkout — update with `git pull` (and `uv sync` if needed)."
    return (
        "Couldn't detect the install method. Update manually with one of:\n"
        f"  uv tool upgrade {PYPI_NAME}\n"
        f"  pipx upgrade {PYPI_NAME}\n"
        f"  pip install --upgrade {PYPI_NAME}"
    )
