"""fastembed keeps its model in a per-user cache, not in the system temp directory.

Left to itself fastembed caches under `tempfile.gettempdir()`, which the OS
clears; the next process then re-downloads the model (~32 s for bge-small, and
an offline recall falls back to hashing). ADR 0020.
"""
from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path

from torsor_helper import embeddings


def _capture(monkeypatch) -> dict:
    seen: dict = {}

    class FakeTextEmbedding:
        def __init__(self, model_name, cache_dir=None, **kwargs):
            seen["model"] = model_name
            seen["cache_dir"] = cache_dir

    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(TextEmbedding=FakeTextEmbedding))
    return seen


def test_the_model_is_cached_per_user_not_in_temp(monkeypatch, tmp_path):
    monkeypatch.delenv("FASTEMBED_CACHE_PATH", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    # tmp_path is itself under the real temp dir, so point "system temp" elsewhere
    # or a correct per-user path would look like a temp path.
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "systmp"))
    seen = _capture(monkeypatch)

    embeddings._make_fastembed("BAAI/bge-small-en-v1.5")

    assert seen["cache_dir"] == str(tmp_path / "home" / ".cache" / "torsor-helper" / "fastembed")
    assert not Path(seen["cache_dir"]).is_relative_to(tempfile.gettempdir())


def test_xdg_cache_home_is_honoured(monkeypatch, tmp_path):
    monkeypatch.delenv("FASTEMBED_CACHE_PATH", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    seen = _capture(monkeypatch)

    embeddings._make_fastembed("m")

    assert seen["cache_dir"] == str(tmp_path / "xdg" / "torsor-helper" / "fastembed")


def test_fastembeds_own_variable_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("FASTEMBED_CACHE_PATH", str(tmp_path / "mine"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    seen = _capture(monkeypatch)

    embeddings._make_fastembed("m")

    assert seen["cache_dir"] == str(tmp_path / "mine")
