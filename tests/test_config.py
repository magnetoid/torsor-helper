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
