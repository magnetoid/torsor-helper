import json

import pytest

from torsor_helper.clients import SUPPORTED_CLIENTS, config_snippet


def test_supported_clients_present():
    for key in ("claude-code", "claude-desktop", "cursor", "windsurf", "vscode", "codex", "gemini"):
        assert key in SUPPORTED_CLIENTS


def test_claude_code_snippet_is_a_command():
    snippet = config_snippet("claude-code", root="/proj")
    assert "claude mcp add" in snippet
    assert "torsor" in snippet
    assert "/proj" in snippet


def test_cursor_snippet_is_valid_json_with_server():
    snippet = config_snippet("cursor", root="/proj")
    data = json.loads(snippet)
    assert "torsor-helper" in data["mcpServers"]
    assert data["mcpServers"]["torsor-helper"]["command"] == "torsor"
    assert "/proj" in data["mcpServers"]["torsor-helper"]["args"]


def test_unknown_client_raises():
    with pytest.raises(KeyError):
        config_snippet("nope", root="/proj")


def test_codex_snippet_is_toml():
    snippet = config_snippet("codex", root="/proj")
    assert "[mcp_servers.torsor-helper]" in snippet
    assert 'command = "torsor"' in snippet
    assert "/proj" in snippet
