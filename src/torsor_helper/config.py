from __future__ import annotations

import tomllib

import tomli_w
from pydantic import BaseModel, Field

from torsor_helper.paths import TorsorPaths

# Per-tier importance floor: a note's recall score is scaled by a multiplier in
# [floor, 1.0] that rises with how often it has been recalled. Stable tiers
# (charter/architecture) have floor 1.0 (never decay); episodic noise can sink
# to its floor until it proves useful. Keyed by Tier.name for TOML friendliness.
_DEFAULT_IMPORTANCE_FLOORS = {
    "CHARTER": 1.0,
    "ARCHITECTURE": 1.0,
    "MAP": 0.9,
    "ACTIVE": 0.85,
    "EPISODIC": 0.7,
}


class BudgetConfig(BaseModel):
    bootstrap_tokens: int = 2000
    recall_tokens: int = 1500
    chars_per_token: int = 4


class EmbeddingConfig(BaseModel):
    # Placeholder for Phase 2; unused in Phase 1.
    provider: str = "fastembed"
    model: str = "BAAI/bge-small-en-v1.5"
    dim: int = 384


class IndexConfig(BaseModel):
    rrf_k: int = 60
    recency_weight: float = 0.1
    graph_boost: float = 0.1
    auto_index: bool = True
    mmr_lambda: float = 0.7  # MMR relevance/diversity trade-off (1.0 = pure relevance)
    importance_floors: dict[str, float] = Field(default_factory=lambda: dict(_DEFAULT_IMPORTANCE_FLOORS))


class TorsorConfig(BaseModel):
    version: int = 1
    budgets: BudgetConfig = Field(default_factory=BudgetConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)


def load_config(paths: TorsorPaths) -> TorsorConfig:
    if not paths.config_file.exists():
        return TorsorConfig()
    with paths.config_file.open("rb") as fh:
        data = tomllib.load(fh)
    return TorsorConfig.model_validate(data)


def save_config(paths: TorsorPaths, config: TorsorConfig) -> None:
    paths.base.mkdir(parents=True, exist_ok=True)
    with paths.config_file.open("wb") as fh:
        tomli_w.dump(config.model_dump(), fh)
