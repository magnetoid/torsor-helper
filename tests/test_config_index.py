from torsor_helper.config import TorsorConfig


def test_index_config_defaults():
    cfg = TorsorConfig()
    assert cfg.index.rrf_k == 60
    assert cfg.index.recency_weight == 0.1
    assert cfg.index.graph_boost == 0.1
    assert cfg.index.auto_index is True
    assert cfg.embeddings.dim == 384
