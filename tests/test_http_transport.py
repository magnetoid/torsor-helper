import torsor_helper.server as srv
from mcp.server.fastmcp import FastMCP


def test_run_defaults_to_stdio(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        FastMCP, "run",
        lambda self, transport="stdio", mount_path=None: captured.update(transport=transport),
    )
    srv.run(tmp_path)
    assert captured["transport"] == "stdio"


def test_run_http_sets_transport_host_port(tmp_path, monkeypatch):
    captured = {}

    def fake_run(self, transport="stdio", mount_path=None):
        captured.update(transport=transport, host=self.settings.host, port=self.settings.port)

    monkeypatch.setattr(FastMCP, "run", fake_run)
    srv.run(tmp_path, transport="streamable-http", host="0.0.0.0", port=9001)
    assert captured["transport"] == "streamable-http"
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9001
