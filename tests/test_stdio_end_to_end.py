"""Speak JSON-RPC to the real binary, the way an MCP client does.

Everything else stubs FastMCP.run or calls build_server() in-process, so the
actual shipped entry point — the `torsor` console script, its imports, its
argument parsing, the server it constructs — was never exercised. A broken
console-script or an import-time failure would have passed CI and shipped.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

pytestmark = pytest.mark.slow


class _Client:
    """The smallest MCP client that can hold a conversation over stdio."""

    def __init__(self, proc):
        self.proc = proc
        self._id = 0

    def send(self, method, params=None, *, notify=False):
        message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notify:
            self._id += 1
            message["id"] = self._id
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        if notify:
            return None
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise AssertionError(f"server closed the stream; stderr:\n{self.proc.stderr.read()}")
            reply = json.loads(line)
            if reply.get("id") == self._id:
                return reply


def _entry_point():
    """The console script if it is installed, else `python -m torsor_helper`.
    Both are shipped entry points and both must work."""
    script = Path(sys.executable).parent / "torsor"
    return [str(script)] if script.exists() else [sys.executable, "-m", "torsor_helper"]


@pytest.fixture
def client(tmp_path):
    Store(TorsorPaths(tmp_path)).scaffold()
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        [*_entry_point(), "mcp", "--root", str(tmp_path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env,
    )
    c = _Client(proc)
    try:
        init = c.send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        })
        assert "result" in init, init
        c.send("notifications/initialized", notify=True)
        yield c
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_the_server_introduces_itself(client):
    reply = client.send("tools/list")
    names = {t["name"] for t in reply["result"]["tools"]}
    assert {"recall", "remember", "bootstrap_session", "verify", "stats"} <= names


def test_a_tool_call_round_trips(client):
    reply = client.send("tools/call", {"name": "get_rules", "arguments": {}})
    assert "result" in reply, reply
    text = reply["result"]["content"][0]["text"]
    assert isinstance(text, str) and text


def test_writing_then_reading_memory_over_the_wire(client):
    client.send("tools/call", {"name": "remember",
                               "arguments": {"content": "we chose SQLite", "kind": "decision"}})
    reply = client.send("tools/call", {"name": "recall", "arguments": {"query": "SQLite"}})
    assert "SQLite" in reply["result"]["content"][0]["text"]


def test_prompts_and_resources_are_reachable(client):
    prompts = {p["name"] for p in client.send("prompts/list")["result"]["prompts"]}
    assert {"onboard", "checkpoint"} <= prompts

    uris = {r["uri"] for r in client.send("resources/list")["result"]["resources"]}
    assert "torsor://charter" in uris


def test_an_unknown_tool_is_an_error_not_a_crash(client):
    reply = client.send("tools/call", {"name": "no_such_tool", "arguments": {}})
    assert "error" in reply or reply["result"].get("isError")
    assert client.send("tools/list")["result"]["tools"], "the server died on a bad call"


def test_python_dash_m_is_also_an_entry_point(tmp_path):
    """Not everyone has the console script on PATH — a container, a CI step
    with only the interpreter, an unactivated venv."""
    Store(TorsorPaths(tmp_path)).scaffold()
    out = subprocess.run(
        [sys.executable, "-m", "torsor_helper", "doctor", "--root", str(tmp_path)],
        capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stderr
    assert "healthy" in out.stdout
