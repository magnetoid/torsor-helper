import anyio

from torsor_helper.server import build_server


def test_server_registers_map_and_bootstrap(tmp_path):
    server = build_server(tmp_path)
    tools = anyio.run(server.list_tools)
    names = {t.name for t in tools}
    assert {"map_repo", "bootstrap_session"} <= names and "get_intent" not in names
