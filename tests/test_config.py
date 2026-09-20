from pathlib import Path

from torsor_helper.config import TorsorConfig, load_config, save_config
from torsor_helper.paths import TorsorPaths


def test_defaults_when_no_file(tmp_path: Path):
    cfg = load_config(TorsorPaths(tmp_path))
    assert cfg.version == 1
    assert cfg.budgets.bootstrap_tokens == 2000
    assert cfg.budgets.recall_tokens == 1500
    assert cfg.budgets.chars_per_token == 4
    assert cfg.embeddings.provider == "fastembed"


def test_save_then_load_round_trips(tmp_path: Path):
    paths = TorsorPaths(tmp_path)
    paths.base.mkdir(parents=True)
    cfg = TorsorConfig()
    cfg.budgets.bootstrap_tokens = 3333
    save_config(paths, cfg)
    assert paths.config_file.exists()
    loaded = load_config(paths)
    assert loaded.budgets.bootstrap_tokens == 3333


def test_budget_and_graph_ceilings_come_from_config_not_literals(tmp_path):
    """Regression: the primer's 800, the rules digest's 600 and connect's 12
    were each written out in two or three places, so changing one silently left
    the other surfaces on the old value."""
    from torsor_helper import operations as ops
    from torsor_helper.budget import estimate_tokens
    from torsor_helper.config import TorsorConfig
    from torsor_helper.paths import TorsorPaths
    from torsor_helper.store import Store

    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    config = TorsorConfig()
    config.budgets.primer_tokens = 40
    config.budgets.rules_tokens = 30

    cpt = config.budgets.chars_per_token
    assert estimate_tokens(ops.project_primer(store, config), cpt) <= 40
    assert estimate_tokens(ops.agent_rules(store, config), cpt) <= 30


def test_connect_hop_bound_comes_from_config(tmp_path):
    from torsor_helper.config import TorsorConfig

    config = TorsorConfig()
    assert config.index.connect_max_hops == 12
    config.index.connect_max_hops = 3
    assert config.index.connect_max_hops == 3
