import anyio

from torsor_mem.server import build_server


def test_server_registers_expected_tools(tmp_path):
    server = build_server(tmp_path)
    assert server.name == "torsor-mem"
    tools = anyio.run(server.list_tools)
    names = {t.name for t in tools}
    assert {"bootstrap_session", "recall", "remember", "update_active", "handoff"} <= names


def test_server_resources_registered(tmp_path):
    server = build_server(tmp_path)
    resources = anyio.run(server.list_resources)
    uris = {str(r.uri) for r in resources}
    assert any(u.startswith("torsor://") for u in uris)
