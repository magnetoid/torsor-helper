"""The MCP server loads the embedder in the background as it starts.

With fastembed installed, importing it and loading the model costs 1.6-2.4 s
per server process (measured on janus), and that used to land on the agent's
first `recall`. A server is started before the agent's first turn and the first
recall comes turns later, so the load can run in that gap instead.
"""
from __future__ import annotations

import threading
import time

from torsor_helper import server
from torsor_helper.embeddings import HashingEmbedder
from torsor_helper.operations import _shared
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def _project(tmp_path, provider: str) -> TorsorPaths:
    paths = TorsorPaths(tmp_path)
    Store(paths).scaffold()
    paths.config_file.write_text(f'[embeddings]\nprovider = "{provider}"\n', encoding="utf-8")
    return paths


def _counting(monkeypatch, delay: float = 0.0) -> list[str]:
    calls: list[str] = []

    def fake(config):
        calls.append(config.embeddings.provider)
        time.sleep(delay)
        return HashingEmbedder(config.embeddings.dim)

    monkeypatch.setattr(_shared, "get_embedder", fake)
    monkeypatch.setattr(_shared, "_EMBEDDER_CACHE", {})
    return calls


def test_warmup_loads_fastembed_once_and_recall_reuses_it(tmp_path, monkeypatch):
    calls = _counting(monkeypatch)
    paths = _project(tmp_path, "fastembed")

    thread = _shared.start_embedder_warmup(paths)
    assert thread is not None
    thread.join(5)

    from torsor_helper.config import load_config
    _shared._embedder_for(load_config(paths))
    assert calls == ["fastembed"]


def test_a_recall_during_the_warmup_waits_for_it_instead_of_loading_twice(tmp_path, monkeypatch):
    calls = _counting(monkeypatch, delay=0.3)
    paths = _project(tmp_path, "fastembed")
    from torsor_helper.config import load_config
    config = load_config(paths)

    thread = _shared.start_embedder_warmup(paths)
    time.sleep(0.05)  # the warm-up is now inside get_embedder
    racer = threading.Thread(target=_shared._embedder_for, args=(config,))
    racer.start()
    thread.join(5)
    racer.join(5)
    assert calls == ["fastembed"]


def test_no_warmup_for_the_hashing_embedder(tmp_path, monkeypatch):
    calls = _counting(monkeypatch)
    assert _shared.start_embedder_warmup(_project(tmp_path, "hashing")) is None
    assert calls == []


def test_no_warmup_without_a_project_or_with_a_broken_config(tmp_path, monkeypatch):
    calls = _counting(monkeypatch)
    assert _shared.start_embedder_warmup(TorsorPaths(tmp_path)) is None
    paths = _project(tmp_path, "fastembed")
    paths.config_file.write_text("[embeddings]\nprovidr = 'fastembed'\n", encoding="utf-8")
    assert _shared.start_embedder_warmup(paths) is None
    assert calls == []


def test_the_server_starts_the_warmup_before_serving(tmp_path, monkeypatch):
    order: list[str] = []
    monkeypatch.setattr(server.ops, "start_embedder_warmup", lambda paths: order.append("warm"))
    monkeypatch.setattr(server.MCPServer, "run", lambda self, transport: order.append("serve"))
    _project(tmp_path, "fastembed")
    server.run(tmp_path)
    assert order == ["warm", "serve"]
