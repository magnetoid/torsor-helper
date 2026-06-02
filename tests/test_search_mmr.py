from datetime import datetime

import numpy as np

from torsor_helper import db
from torsor_helper.config import TorsorConfig
from torsor_helper.embeddings import HashingEmbedder
from torsor_helper.indexer import reindex
from torsor_helper.models import RecallHit, Tier
from torsor_helper.paths import TorsorPaths
from torsor_helper.search import _mmr_order, hybrid_search
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _hit(path, score):
    return RecallHit(path=path, title=path, tier=Tier.EPISODIC, score=score, snippet="body")


def test_mmr_demotes_near_duplicate():
    hits = [_hit("x", 1.0), _hit("y", 0.9), _hit("z", 0.8)]
    vecs = {
        "x": np.array([1.0, 0.0, 0.0]),
        "y": np.array([0.99, 0.01, 0.0]),  # near-duplicate of x
        "z": np.array([0.0, 1.0, 0.0]),    # distinct, slightly lower relevance
    }
    order = [h.path for h in _mmr_order(hits, vecs, 0.7)]
    assert order[0] == "x"
    assert order[1] == "z"  # diverse z beats near-dup y despite lower score


def test_mmr_noop_without_two_vectors():
    hits = [_hit("x", 1.0), _hit("y", 0.9)]
    order = [h.path for h in _mmr_order(hits, {"x": np.array([1.0, 0.0, 0.0])}, 0.7)]
    assert order == ["x", "y"]  # <2 vectors → untouched (keyword/hashing paths safe)


def test_mmr_deterministic():
    hits = [_hit("x", 1.0), _hit("y", 0.9), _hit("z", 0.8)]
    vecs = {"x": np.array([1.0, 0.0, 0.0]), "y": np.array([0.99, 0.01, 0.0]), "z": np.array([0.0, 1.0, 0.0])}
    assert [h.path for h in _mmr_order(hits, vecs, 0.7)] == [h.path for h in _mmr_order(hits, vecs, 0.7)]


def _indexed(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    conn = db.connect(tmp_path / "i.db")
    reindex(store, conn, HashingEmbedder(dim=128))
    return store, conn


def test_budget_omitted_marker_appears_on_truncation(tmp_path):
    store, conn = _indexed(tmp_path)
    res = hybrid_search(conn, HashingEmbedder(dim=128), TorsorConfig(), "architecture context", limit=8, max_tokens=1)
    assert res.hits
    marker = res.hits[-1]
    assert "omitted" in marker.title and marker.title.startswith("…")
    assert marker.path == ""  # sentinel, not a real note


def test_no_marker_when_not_truncated(tmp_path):
    store, conn = _indexed(tmp_path)
    res = hybrid_search(conn, HashingEmbedder(dim=128), TorsorConfig(), "architecture context", limit=8, max_tokens=1_000_000)
    assert not any("omitted" in h.title for h in res.hits)


def test_omitted_marker_count_reflects_full_pool(tmp_path):
    import re

    store, conn = _indexed(tmp_path)
    # tiny limit AND tiny budget so the marker fires and the full pool exceeds limit
    res = hybrid_search(conn, HashingEmbedder(dim=128), TorsorConfig(), "architecture context", limit=2, max_tokens=1)
    real = [h for h in res.hits if h.path]
    assert res.hits[-1].path == ""  # marker present
    m = re.search(r"… (\d+) more", res.hits[-1].title)
    assert m
    # count = full relevant pool minus what was shown (not the limit-capped candidate set)
    total = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    assert int(m.group(1)) == total - len(real)
