# How to install torsor-helper

torsor-helper is a small, local-first Python package (Python ≥ 3.11). It runs entirely on your machine: no API key, no account, no model download required (semantic embeddings are an optional extra).

**Contents:** [Install the CLI](#1-install-the-torsor-cli) · [Set up your project](#2-set-up-your-project) · [Connect your coding agent](#3-connect-your-coding-agent) · [Optional extras](#4-optional-extras) · [Verify](#5-verify-the-install) · [Upgrade / uninstall](#6-upgrade--uninstall) · [Troubleshooting](#troubleshooting)

## 1. Install the `torsor` CLI

### Recommended: `uv tool install` (or `pipx`)

Installs the global `torsor` command straight from GitHub — no PyPI needed:

```bash
uv tool install "git+https://github.com/magnetoid/torsor-helper"
# or:
pipx install "git+https://github.com/magnetoid/torsor-helper"
```

With semantic embeddings (downloads a small local model on first use; everything still runs offline afterwards):

```bash
uv tool install "torsor-helper[embeddings] @ git+https://github.com/magnetoid/torsor-helper"
```

### Once published to PyPI

```bash
uv tool install torsor-helper      # or: pipx install torsor-helper / pip install torsor-helper
uvx torsor-helper --help           # ephemeral run, no install
```

### One-liner (installs + wires up the current project)

Paste into your terminal (or directly into the Claude Code terminal) from inside your project:

```bash
curl -fsSL https://raw.githubusercontent.com/magnetoid/torsor-helper/main/scripts/install.sh | bash
```

It installs `torsor`, scaffolds `.torsor/`, and writes a project `.mcp.json`. Use `install.sh --global` to register the MCP server for all projects instead.

### From a local clone (for development)

```bash
git clone https://github.com/magnetoid/torsor-helper && cd torsor-helper
uv run torsor --help               # uv resolves the env from pyproject automatically
```

## 2. Set up your project

```bash
cd your-project
torsor init --write          # scaffold .torsor/ AND write a project .mcp.json
torsor doctor                # sanity-check
```

- **Commit `.torsor/`** — it is your project's memory (plain Markdown; the derived `.torsor/.index/` is gitignored automatically).
- `--write` drops a `.mcp.json` so clients that read it (Claude Code especially) auto-detect torsor-helper.

## 3. Connect your coding agent

torsor-helper is a standard **MCP stdio server** (`torsor mcp`). For any of the 20 supported clients, one command prints the exact snippet **and where to paste it**:

```bash
torsor init --client <name>
```

| Client | `--client` key | Config goes in |
|---|---|---|
| Claude Code | `claude-code` | project `.mcp.json` (auto via `torsor init --write`) or `claude mcp add torsor-helper -- torsor mcp` |
| Claude Desktop | `claude-desktop` | `claude_desktop_config.json` (Settings → Developer → Edit Config) |
| Cursor | `cursor` | `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global) |
| Windsurf | `windsurf` | `~/.codeium/windsurf/mcp_config.json` (Settings → Cascade → MCP) |
| VS Code / Copilot | `vscode` | `.vscode/mcp.json` — note: VS Code uses a `servers` key, the snippet handles it |
| GitHub Copilot CLI | `copilot-cli` | `~/.copilot/mcp-config.json` (or `/mcp add` inside the CLI) |
| Codex CLI | `codex` | `~/.codex/config.toml` (TOML — the snippet handles it) |
| Gemini CLI | `gemini` | `~/.gemini/settings.json` or project `.gemini/settings.json` |
| Google Antigravity | `antigravity` | Agent panel → settings → MCP Servers → Manage (`mcp_config.json`) |
| Cline | `cline` | `cline_mcp_settings.json` (Cline → MCP Servers → Configure) |
| Roo Code | `roo` | `mcp_settings.json` (Roo → MCP Servers → Edit settings) |
| Trae | `trae` | AI chat → Settings → MCP → Add manually |
| Kiro | `kiro` | `.kiro/settings/mcp.json` (project) or `~/.kiro/settings/mcp.json` |
| Warp | `warp` | Settings → AI → Manage MCP servers |
| Zed | `zed` | `settings.json` (`context_servers` shape — the snippet handles it) |
| JetBrains AI / Junie | `jetbrains` | Settings → Tools → AI Assistant → Model Context Protocol → Add |
| Continue | `continue` | `.continue/config.yaml` (YAML — the snippet handles it) |
| OpenCode | `opencode` | `opencode.json` (its own `mcp` shape — the snippet handles it) |
| Amp | `amp` | VS Code `settings.json` under `amp.mcpServers` |
| Goose | `goose` | `~/.config/goose/config.yaml` (or `goose configure`) |

> **PATH note:** the snippets use `command: "torsor"`, which requires `torsor` on your PATH (that's what `uv tool install` / `pipx install` do). To run ephemerally instead, use `"command": "uvx", "args": ["torsor-helper", "mcp"]`.

## 4. Optional extras

| Extra | What it adds | Install |
|---|---|---|
| `embeddings` | Real semantic vectors via [fastembed](https://github.com/qdrant/fastembed) (BAAI/bge-small by default) instead of the offline hashing fallback | `uv tool install "torsor-helper[embeddings] @ git+https://github.com/magnetoid/torsor-helper"` |

Without the extra, recall uses a deterministic offline hashing embedder — every feature still works with no model download and no API key. Graceful degradation is a design rule.

## 5. Verify the install

```bash
torsor --version             # → torsor-helper 0.3.0
torsor doctor                # → OK: torsor-helper project is healthy.
```

In your agent, ask it to call `bootstrap_session()` — you should get back your charter, architecture, and active context. (In Claude Code, `/mcp` lists connected servers.)

## 6. Upgrade / uninstall

```bash
torsor update                          # detects uv tool / pipx / pip and runs the right upgrade
uv tool upgrade torsor-helper          # or: pipx upgrade torsor-helper
uv tool uninstall torsor-helper        # or: pipx uninstall torsor-helper
```

Your memory lives in `.torsor/` in each project and is untouched by upgrades. The derived index (`.torsor/.index/`) is disposable — delete it any time; the next `torsor index` (or any recall) rebuilds it.

## Troubleshooting

- **`torsor: command not found`** — the tool-install bin dir isn't on PATH. Run `uv tool update-shell` (or `pipx ensurepath`) and restart the shell, or use the `uvx` form in the client config.
- **Client doesn't see the server** — check the config went into the file listed in the table above, then fully restart/reload the client (most only read MCP config at startup).
- **`torsor doctor` fails** — run `torsor init` first (it never overwrites existing files unless you pass `--force`).
- **Recall feels keyword-only** — you're on the hashing fallback; install the `embeddings` extra for semantic recall.
- **Two machines / teammates** — commit `.torsor/`, never `.torsor/.index/` (the scaffold's `.gitignore` already handles this). Each machine derives its own index.
