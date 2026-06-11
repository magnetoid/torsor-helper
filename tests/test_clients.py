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


def test_every_supported_client_has_snippet_and_location():
    from torsor_helper.clients import config_location

    for key in SUPPORTED_CLIENTS:
        snippet = config_snippet(key, root="/proj")
        assert "torsor" in snippet and "/proj" in snippet
        assert config_location(key)  # every client documents where the config goes


def test_new_vibe_coding_clients_present():
    for key in ("antigravity", "zed", "jetbrains", "continue", "opencode", "amp", "goose", "copilot-cli"):
        assert key in SUPPORTED_CLIENTS


def test_vscode_snippet_uses_servers_shape():
    data = json.loads(config_snippet("vscode", root="/proj"))
    assert data["servers"]["torsor-helper"]["type"] == "stdio"
    assert data["servers"]["torsor-helper"]["command"] == "torsor"


def test_zed_snippet_uses_context_servers():
    data = json.loads(config_snippet("zed", root="/proj"))
    assert data["context_servers"]["torsor-helper"]["command"] == "torsor"


def test_opencode_snippet_shape():
    data = json.loads(config_snippet("opencode", root="/proj"))
    assert data["mcp"]["torsor-helper"]["command"][0] == "torsor"
    assert data["mcp"]["torsor-helper"]["type"] == "local"


def test_antigravity_snippet_is_standard_mcp_servers_block():
    data = json.loads(config_snippet("antigravity", root="/proj"))
    assert data["mcpServers"]["torsor-helper"]["command"] == "torsor"
