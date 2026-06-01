import anyio

from torsor_helper.server import build_server


def test_server_registers_map_and_intent(tmp_path):
    server = build_server(tmp_path)
    tools = anyio.run(server.list_tools)
    names = {t.name for t in tools}
    assert {"map_repo", "get_intent"} <= names
