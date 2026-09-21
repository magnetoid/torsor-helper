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


def test_the_http_transport_actually_binds_and_serves(tmp_path):
    """The two tests above monkeypatch FastMCP.run, so they check argument
    plumbing and nothing else — no port is ever bound. This one starts the real
    server and talks to it."""
    import json
    import os
    import socket
    import subprocess
    import sys
    import time
    import urllib.error
    import urllib.request
    from pathlib import Path

    import pytest

    from torsor_helper.paths import TorsorPaths
    from torsor_helper.store import Store

    Store(TorsorPaths(tmp_path)).scaffold()
    with socket.socket() as probe:          # a port nobody else holds
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    script = Path(sys.executable).parent / "torsor"
    argv = ([str(script)] if script.exists() else [sys.executable, "-m", "torsor_helper"])
    proc = subprocess.Popen(
        [*argv, "mcp", "--root", str(tmp_path), "--http", "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    url = f"http://127.0.0.1:{port}/mcp"
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "t", "version": "0"}},
    }).encode()
    request = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    })
    try:
        # 90s, not 30s: this spawns an interpreter that imports mcp/fastmcp and
        # binds a port, and it failed once under `-n auto` on a loaded machine
        # while the process was still alive and simply not up yet. CI runners
        # are slower and shared, and a flaky test inside the release gate blocks
        # a publish for no reason.
        deadline = time.monotonic() + 90
        last = None
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                pytest.fail(f"server exited: {proc.stderr.read()}")
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    payload = response.read().decode()
                    assert "torsor-helper" in payload, payload
                    return
            except urllib.error.HTTPError as exc:      # it answered, which is the point
                assert exc.code < 500, exc.read().decode()
                return
            except (urllib.error.URLError, ConnectionError, OSError) as exc:
                last = exc
                time.sleep(0.3)
        # Drain the server's own output before failing — a bare "connection
        # refused" says nothing about why it never bound. Terminate first:
        # stderr.read() blocks until EOF, and the process is still running here.
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        pytest.fail(f"never became reachable on {url}: {last}\n{proc.stderr.read()}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
