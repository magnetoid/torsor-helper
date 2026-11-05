import anyio

from torsor_helper.server import build_server


def test_server_registers_expected_tools(tmp_path):
    server = build_server(tmp_path)
    assert server.name == "torsor-helper"
    tools = anyio.run(server.list_tools)
    names = {t.name for t in tools}
    assert {"bootstrap_session", "recall", "remember", "update_active", "handoff", "connect"} <= names


def test_server_resources_registered(tmp_path):
    server = build_server(tmp_path)
    resources = anyio.run(server.list_resources)
    uris = {str(r.uri) for r in resources}
    assert any(u.startswith("torsor://") for u in uris)


def test_a_tool_result_carries_its_text_once(tmp_path):
    # Every tool returns a string. Left on, the SDK's structured output sends it
    # twice — as content and again as {"result": <same text>} — and advertises
    # an output schema per tool, all of it billed to the agent's context.
    from torsor_helper.paths import TorsorPaths
    from torsor_helper.store import Store

    Store(TorsorPaths(tmp_path)).scaffold()
    server = build_server(tmp_path)

    result = anyio.run(lambda: server.call_tool("list_commands", {}))
    assert result.content[0].text
    assert result.structured_content is None
    assert all(t.output_schema is None for t in anyio.run(server.list_tools))
