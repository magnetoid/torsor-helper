from __future__ import annotations

import json
from pathlib import Path

# Human-readable label per supported client key.
SUPPORTED_CLIENTS: dict[str, str] = {
    "claude-code": "Claude Code",
    "claude-desktop": "Claude Desktop",
    "cursor": "Cursor",
    "windsurf": "Windsurf",
    "vscode": "VS Code / Copilot",
    "codex": "Codex",
    "gemini": "Gemini CLI",
    "cline": "Cline",
    "roo": "Roo Code",
    "trae": "Trae",
    "kiro": "Kiro",
    "warp": "Warp",
}


def mcp_servers_block(root: str) -> dict:
    """The standard `mcpServers` JSON block that registers torsor-helper.

    Consumed by every JSON-config MCP client (Claude Code via project `.mcp.json`,
    Cursor, Windsurf, Cline, Roo, VS Code, ...).
    """
    return {"mcpServers": {"torsor-helper": {"command": "torsor", "args": ["mcp", "--root", root]}}}


def config_snippet(client: str, root: str) -> str:
    # claude-code is configured via a CLI command; every other supported
    # client consumes the same JSON mcpServers block (file location varies).
    if client not in SUPPORTED_CLIENTS:
        raise KeyError(client)
    if client == "claude-code":
        return f'claude mcp add torsor-helper -- torsor mcp --root "{root}"'
    if client == "codex":
        # Codex CLI uses TOML at ~/.codex/config.toml, not the mcpServers JSON block.
        return (
            "# add to ~/.codex/config.toml\n"
            "[mcp_servers.torsor-helper]\n"
            'command = "torsor"\n'
            f'args = ["mcp", "--root", "{root}"]\n'
        )
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
