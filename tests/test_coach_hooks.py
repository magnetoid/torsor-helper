import anyio

from torsor_helper.paths import TorsorPaths
from torsor_helper.server import build_server
from torsor_helper.store import Store


def test_scaffold_creates_insights_dir(tmp_path):
    paths = TorsorPaths(tmp_path)
    Store(paths).scaffold()
    assert paths.insights_dir.is_dir()
    assert paths.insights_dir == paths.memory_dir / "insights"


def test_server_registers_recommend_stub(tmp_path):
    server = build_server(tmp_path)
    tools = anyio.run(server.list_tools)
    assert "recommend" in {t.name for t in tools}
