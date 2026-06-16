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
    "copilot-cli": "GitHub Copilot CLI",
    "codex": "Codex CLI",
    "gemini": "Gemini CLI",
    "antigravity": "Google Antigravity",
    "cline": "Cline",
    "roo": "Roo Code",
    "trae": "Trae",
    "kiro": "Kiro",
    "warp": "Warp",
    "zed": "Zed",
    "jetbrains": "JetBrains AI Assistant / Junie",
    "continue": "Continue",
    "opencode": "OpenCode",
    "amp": "Amp",
    "goose": "Goose",
}

# Where each client's MCP config lives (shown next to the snippet so users
# don't have to hunt the docs). Best-effort: locations occasionally move
# between client releases.
CONFIG_LOCATIONS: dict[str, str] = {
    "claude-code": "project .mcp.json (via `torsor init --write`) or `claude mcp add`",
    "claude-desktop": "claude_desktop_config.json (Settings → Developer → Edit Config)",
    "cursor": ".cursor/mcp.json (project) or ~/.cursor/mcp.json (global)",
    "windsurf": "~/.codeium/windsurf/mcp_config.json (Settings → Cascade → MCP)",
    "vscode": ".vscode/mcp.json (project), or Command Palette → 'MCP: Add Server'",
    "copilot-cli": "~/.copilot/mcp-config.json (or `/mcp add` inside the CLI)",
    "codex": "~/.codex/config.toml",
    "gemini": "~/.gemini/settings.json (global) or .gemini/settings.json (project)",
    "antigravity": "Agent panel → settings → MCP Servers → Manage (mcp_config.json)",
    "cline": "cline_mcp_settings.json (Cline → MCP Servers → Configure)",
    "roo": "mcp_settings.json (Roo → MCP Servers → Edit settings)",
    "trae": "Trae → AI chat → Settings → MCP → Add manually",
    "kiro": ".kiro/settings/mcp.json (project) or ~/.kiro/settings/mcp.json",
    "warp": "Warp → Settings → AI → Manage MCP servers",
    "zed": "settings.json (Command Palette → 'zed: open settings')",
    "jetbrains": "Settings → Tools → AI Assistant → Model Context Protocol → Add",
    "continue": ".continue/config.yaml (project) or ~/.continue/config.yaml",
    "opencode": "opencode.json (project) or ~/.config/opencode/opencode.json",
    "amp": "VS Code settings.json (`amp.mcpServers`) or ~/.config/amp/settings.json",
    "goose": "~/.config/goose/config.yaml (or `goose configure`)",
}


# The conventional agent-instructions file per client — where a managed rules /
# primer / model-policy block belongs. AGENTS.md is the cross-tool standard
# (adopted by Codex, Cursor, and many others); a few clients use their own.
INSTRUCTIONS_FILES: dict[str, str] = {
    "claude-code": "CLAUDE.md",
    "claude-desktop": "CLAUDE.md",
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
    Cursor, Windsurf, Cline, Roo, VS Code, ...).
    """
    return {"mcpServers": {"torsor-helper": {"command": "torsor", "args": ["mcp", "--root", root]}}}


def config_snippet(client: str, root: str) -> str:
    # claude-code is configured via a CLI command; most other clients consume
    # the standard JSON mcpServers block (file location varies), and a handful
    # use their own shape (VS Code `servers`, Zed `context_servers`, TOML, YAML).
    if client not in SUPPORTED_CLIENTS:
        raise KeyError(client)
    server = {"command": "torsor", "args": ["mcp", "--root", root]}
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
    if client == "vscode":
        # VS Code's .vscode/mcp.json uses a `servers` key with an explicit type.
        return json.dumps({"servers": {"torsor-helper": {"type": "stdio", **server}}}, indent=2)
    if client == "zed":
        # Zed registers MCP servers as `context_servers` in settings.json.
        return json.dumps({"context_servers": {"torsor-helper": {"source": "custom", **server}}}, indent=2)
    if client == "opencode":
        return json.dumps(
            {"mcp": {"torsor-helper": {"type": "local", "command": ["torsor", "mcp", "--root", root],
                                       "enabled": True}}},
            indent=2,
        )
    if client == "amp":
        return json.dumps({"amp.mcpServers": {"torsor-helper": server}}, indent=2)
    if client == "continue":
        return (
            "# add to config.yaml\n"
            "mcpServers:\n"
            "  - name: torsor-helper\n"
            "    command: torsor\n"
            f'    args: ["mcp", "--root", "{root}"]\n'
        )
    if client == "goose":
        return (
            "# add to ~/.config/goose/config.yaml under `extensions:`\n"
            "extensions:\n"
            "  torsor-helper:\n"
            "    type: stdio\n"
            "    enabled: true\n"
            "    cmd: torsor\n"
            f'    args: ["mcp", "--root", "{root}"]\n'
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
