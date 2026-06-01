from __future__ import annotations

import tomllib

import tomli_w
from pydantic import BaseModel, Field

from torsor_helper.paths import TorsorPaths


class BudgetConfig(BaseModel):
    bootstrap_tokens: int = 2000
    recall_tokens: int = 1500
    chars_per_token: int = 4


class EmbeddingConfig(BaseModel):
    # Placeholder for Phase 2; unused in Phase 1.
    provider: str = "fastembed"
    model: str = "BAAI/bge-small-en-v1.5"


class TorsorConfig(BaseModel):
    version: int = 1
    budgets: BudgetConfig = Field(default_factory=BudgetConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)


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
