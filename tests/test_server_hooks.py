import anyio

from torsor_helper.server import build_server


def test_hooks_have_no_mcp_surface_at_all(tmp_path):
    # hooks_status was the one read-only hooks tool; it is operator information
    # (`torsor hooks status`, `torsor doctor`) that an agent never acts on.
    tools = anyio.run(build_server(tmp_path).list_tools)
    names = {t.name for t in tools}
    assert "hooks_status" not in names


def test_install_uninstall_are_not_mcp_tools(tmp_path):
    # Footgun parity with the self-updater (ADR 0009): an agent must not be able
    # to rewrite its own git hooks / .claude settings — those stay CLI-only.
    tools = anyio.run(build_server(tmp_path).list_tools)
    names = {t.name for t in tools}
    assert "install_hooks" not in names
    assert "uninstall_hooks" not in names
