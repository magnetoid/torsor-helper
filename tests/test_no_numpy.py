"""numpy and tomli-w are gone from the required dependencies.

numpy was the single most expensive import in the process and was used by four
functions that pack, unpack or rank a vector. Those now run on `array('f')` and
plain Python, with numpy used only as an accelerator when something else (the
`[embeddings]` extra) already installed it. tomli-w wrote one file, torsor.toml,
once, at `torsor init`.
"""
from __future__ import annotations

import math
import subprocess
import sys
import tomllib

import pytest

from torsor_helper import db
from torsor_helper.config import TorsorConfig, load_config, save_config
from torsor_helper.paths import TorsorPaths
from torsor_helper.search import _mmr_order

BLOCK = "import sys; sys.modules['numpy'] = None; sys.modules['tomli_w'] = None\n"


def _run_without_numpy(code: str, cwd) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", BLOCK + code], cwd=cwd, capture_output=True, text=True, timeout=120,
    )


def test_recall_works_end_to_end_with_numpy_and_tomli_w_uninstalled(tmp_path):
    code = """
from pathlib import Path
from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig, load_config, save_config
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store
root = Path.cwd()
paths = TorsorPaths(root)
save_config(paths, TorsorConfig())
config = load_config(paths)
store = Store.for_config(paths, config)
ops.remember(store, "the payment service retries idempotently")
ops.remember(store, "the login page uses passkeys")
hits = ops.recall(store, config, "payment retries", limit=5).hits
assert hits and "payment" in hits[0].title.lower() + hits[0].snippet.lower(), hits
print("ok")
"""
    proc = _run_without_numpy(code, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


def _norm(vec) -> float:
    return math.sqrt(sum(x * x for x in vec))


@pytest.fixture(params=["pure", "numpy"])
def accelerator(request, monkeypatch):
    if request.param == "pure":
        monkeypatch.setattr(db, "_numpy", lambda: None)
    elif db._numpy() is None:
        pytest.skip("numpy is not installed in this environment")
    return request.param


def test_pack_normalizes_and_unpack_round_trips(accelerator):
    vec = [0.1, -0.2, 0.3]
    out = list(db.unpack(db.pack(vec)))
    assert len(out) == 3
    assert math.isclose(_norm(out), 1.0, abs_tol=1e-6)
    n = _norm(vec)
    assert all(math.isclose(a, b / n, abs_tol=1e-6) for a, b in zip(out, vec))
    assert list(db.unpack(db.pack([0.0, 0.0]))) == [0.0, 0.0]


def test_cosine_search_ranks_the_same_on_both_paths(tmp_path, accelerator):
    conn = db.connect(tmp_path / "t.db")
    for path, vec in [("x.md", [1.0, 0.0]), ("y.md", [0.0, 1.0]), ("z.md", [0.9, 0.1]), ("w.md", [0.9, 0.1])]:
        db.upsert_note(conn, path, "h", 4, "journal", None, path, "t")
        db.upsert_vector(conn, path, vec)
    ranked = db.cosine_search(conn, [1.0, 0.0], 3)
    # ties break by path, so the order is total and identical on both paths
    assert [p for p, _ in ranked] == ["x.md", "w.md", "z.md"]
    assert math.isclose(ranked[0][1], 1.0, abs_tol=1e-6)
    assert db.cosine_search(conn, [0.0, 0.0], 3) == []


def test_mmr_runs_on_unpacked_vectors_without_numpy(monkeypatch):
    monkeypatch.setattr(db, "_numpy", lambda: None)
    from torsor_helper.models import RecallHit

    def hit(path, score):
        return RecallHit(path=path, title=path, snippet="", score=score, tier=4)

    vecs = {p: db.unpack(db.pack(v)) for p, v in
            {"x": [1.0, 0.0, 0.0], "y": [0.99, 0.01, 0.0], "z": [0.0, 1.0, 0.0]}.items()}
    hits = [hit("x", 1.0), hit("y", 0.98), hit("z", 0.9)]
    assert [h.path for h in _mmr_order(hits, vecs, 0.7)] == ["x", "z", "y"]


def test_save_config_writes_toml_that_tomllib_reads_back_identically(tmp_path):
    paths = TorsorPaths(tmp_path)
    cfg = TorsorConfig()
    cfg.memory.sources = ["README.md", "docs/**/*.md", 'odd "quote" name.md']
    cfg.index.recency_weight = 0.25
    cfg.automation.guard_on_push = True
    save_config(paths, cfg)
    text = paths.config_file.read_text()
    assert "tomli" not in text
    assert tomllib.loads(text) == cfg.model_dump()
    assert load_config(paths) == cfg


def test_numpy_and_tomli_w_are_not_required_dependencies():
    import pathlib
    data = tomllib.loads(pathlib.Path("pyproject.toml").read_text())
    required = " ".join(data["project"]["dependencies"])
    assert "numpy" not in required and "tomli" not in required
