import math

from torsor_helper.config import TorsorConfig
from torsor_helper.embeddings import HashingEmbedder, get_embedder


def test_hashing_embedder_is_deterministic_and_normalized():
    e = HashingEmbedder(dim=64)
    a = e.embed(["auth tokens and login"])[0]
    b = e.embed(["auth tokens and login"])[0]
    assert a == b
    assert len(a) == 64
    assert abs(math.sqrt(sum(x * x for x in a)) - 1.0) < 1e-6


def test_hashing_embedder_distinguishes_texts():
    e = HashingEmbedder(dim=64)
    auth = e.embed(["authentication login session"])[0]
    pay = e.embed(["stripe billing invoice"])[0]
    dot = sum(x * y for x, y in zip(auth, pay))
    assert dot < 0.9


def test_empty_text_yields_zero_vector():
    e = HashingEmbedder(dim=8)
    assert e.embed([""])[0] == [0.0] * 8


def test_get_embedder_falls_back_to_hashing(monkeypatch):
    import torsor_helper.embeddings as emb

    def boom(model):
        raise RuntimeError("no fastembed")

    monkeypatch.setattr(emb, "_make_fastembed", boom)
    cfg = TorsorConfig()
    cfg.embeddings.provider = "fastembed"
    cfg.embeddings.dim = 32
    e = get_embedder(cfg)
    assert e.name == "hashing"
    assert e.dim == 32
