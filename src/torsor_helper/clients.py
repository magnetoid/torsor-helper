from __future__ import annotations

import json
from pathlib import Path

# Human-readable label per supported client key. Deliberately short: the
# agents a solo vibe coder actually sits in front of. Every other MCP client
# takes the standard `mcpServers` JSON block that `other` prints.
SUPPORTED_CLIENTS: dict[str, str] = {
    "claude-code": "Claude Code",
    "cursor": "Cursor",
    "codex": "Codex CLI",
    "vscode": "VS Code / Copilot",
    "gemini": "Gemini CLI",
    "other": "Any other MCP client (standard mcpServers JSON)",
}

# Where each client's MCP config lives (shown next to the snippet so users
# don't have to hunt the docs). Best-effort: locations occasionally move
# between client releases.
CONFIG_LOCATIONS: dict[str, str] = {
    "claude-code": "project .mcp.json (via `torsor init --write`) or `claude mcp add`",
    "cursor": ".cursor/mcp.json (project) or ~/.cursor/mcp.json (global)",
    "codex": "~/.codex/config.toml",
    "vscode": ".vscode/mcp.json (project), or Command Palette → 'MCP: Add Server'",
    "gemini": "~/.gemini/settings.json (global) or .gemini/settings.json (project)",
    "other": "your client's MCP settings file — most accept this exact block",
}


# The conventional agent-instructions file per client — where a managed rules /
# primer block belongs. AGENTS.md is the cross-tool standard (read natively by
# Claude Code, Codex and Cursor); a few clients use their own.
INSTRUCTIONS_FILES: dict[str, str] = {
    "claude-code": "CLAUDE.md",
    "gemini": "GEMINI.md",
}


def config_location(client: str) -> str:
    """Where the snippet from config_snippet() should be pasted, per client."""
    return CONFIG_LOCATIONS.get(client, "")


def instructions_file(client: str) -> str:
    """The conventional agent-instructions filename for a client (AGENTS.md by
    default — the cross-tool standard). Override with an explicit `--write` path."""
    return INSTRUCTIONS_FILES.get(client, "AGENTS.md")


def mcp_servers_block(root: str) -> dict:
    """The standard `mcpServers` JSON block that registers torsor-helper.

    Consumed by every JSON-config MCP client (Claude Code via project `.mcp.json`,
    Cursor, Windsurf, Cline, Roo, ...).
    """
    return {"mcpServers": {"torsor-helper": {"command": "torsor", "args": ["mcp", "--root", root]}}}


def config_snippet(client: str, root: str) -> str:
    # claude-code is configured via a CLI command; Codex uses TOML and VS Code
    # its own `servers` key; everything else takes the standard mcpServers block.
    if client not in SUPPORTED_CLIENTS:
        raise KeyError(client)
    server = {"command": "torsor", "args": ["mcp", "--root", root]}
    if client == "claude-code":
        return f'claude mcp add torsor-helper -- torsor mcp --root "{root}"'
    if client == "codex":
        return (
            "# add to ~/.codex/config.toml\n"
            "[mcp_servers.torsor-helper]\n"
            'command = "torsor"\n'
            f'args = ["mcp", "--root", "{root}"]\n'
        )
    if client == "vscode":
        return json.dumps({"servers": {"torsor-helper": {"type": "stdio", **server}}}, indent=2)
    return json.dumps(mcp_servers_block(root), indent=2)


def write_mcp_json(project_root, server_root: str) -> Path:
    """Write/merge a project `.mcp.json` registering torsor-helper, preserving
    any other servers already configured. Returns the path written.

    `.mcp.json` is the de-facto project-scoped MCP config: Claude Code auto-loads
    it, and several other clients accept the same shape.
    """
    target = Path(project_root) / ".mcp.json"
    data: dict = {}
    if target.exists():
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except ValueError:
            data = {}
    servers = data.setdefault("mcpServers", {})
    servers["torsor-helper"] = {"command": "torsor", "args": ["mcp", "--root", server_root]}
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return target
