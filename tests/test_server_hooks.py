import anyio

from torsor_helper.server import build_server


def test_hooks_status_is_registered(tmp_path):
    tools = anyio.run(build_server(tmp_path).list_tools)
    names = {t.name for t in tools}
    assert "hooks_status" in names


def test_install_uninstall_are_not_mcp_tools(tmp_path):
    # Footgun parity with the self-updater (ADR 0009): an agent must not be able
    # to rewrite its own git hooks / .claude settings — those stay CLI-only.
    tools = anyio.run(build_server(tmp_path).list_tools)
    names = {t.name for t in tools}
    assert "install_hooks" not in names
    assert "uninstall_hooks" not in names
