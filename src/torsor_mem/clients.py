from __future__ import annotations

import json

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


def config_snippet(client: str, root: str) -> str:
    # claude-code is configured via a CLI command; every other supported
    # client consumes the same JSON mcpServers block (file location varies).
    if client not in SUPPORTED_CLIENTS:
        raise KeyError(client)
    if client == "claude-code":
        return f'claude mcp add torsor-mem -- torsor mcp --root "{root}"'
    block = {
        "mcpServers": {
            "torsor-mem": {
                "command": "torsor",
                "args": ["mcp", "--root", root],
            }
        }
    }
    return json.dumps(block, indent=2)
