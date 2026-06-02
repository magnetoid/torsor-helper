#!/usr/bin/env bash
# Install torsor-helper (the `torsor` command) and wire it into your project.
#
# Run it straight from the Claude Code terminal:
#   curl -fsSL https://raw.githubusercontent.com/magnetoid/torsor-helper/main/scripts/install.sh | bash
# or from a clone:
#   bash scripts/install.sh
#
# Pass --global to also register torsor-helper with Claude Code for ALL projects
# (via `claude mcp add --scope user`). By default it sets up only the current project.
set -euo pipefail

REPO="git+https://github.com/magnetoid/torsor-helper"
GLOBAL=0
[ "${1:-}" = "--global" ] && GLOBAL=1

say() { printf '\033[36m→\033[0m %s\n' "$1"; }

# 1. Install the `torsor` command (prefer uv, fall back to pipx).
if command -v uv >/dev/null 2>&1; then
  say "Installing torsor-helper with uv…"
  uv tool install --force "$REPO"
elif command -v pipx >/dev/null 2>&1; then
  say "Installing torsor-helper with pipx…"
  pipx install --force "$REPO"
else
  echo "✗ Need 'uv' or 'pipx' on PATH. Install uv (https://docs.astral.sh/uv/) and re-run." >&2
  exit 1
fi
say "Installed: $(command -v torsor)"

# 2. Wire it into Claude Code.
if [ "$GLOBAL" = "1" ] && command -v claude >/dev/null 2>&1; then
  say "Registering with Claude Code for all projects (user scope)…"
  claude mcp add --scope user torsor-helper -- torsor mcp || true
elif [ -d .torsor ] || [ -f pyproject.toml ] || [ -d .git ]; then
  say "Setting up this project (scaffold .torsor/ + write .mcp.json)…"
  torsor init --write
  echo "✓ Claude Code will auto-detect torsor-helper here via .mcp.json. Reload its MCP servers."
else
  echo "ℹ Installed. In a project run:  torsor init --write   (Claude Code auto-detects .mcp.json)"
fi

echo "✓ Done.  Try:  torsor doctor   ·   torsor coach"
