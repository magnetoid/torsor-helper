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


class ModelsConfig(BaseModel):
    # Model-tier policy (token thrift). torsor never calls models — it publishes
    # this routing policy for the orchestrating agent/harness to follow.
    cheap: str = ""   # basic, deterministic work (torsor lookups, command replays)
    smart: str = ""   # thinking & construction (design, code, decisions)
    fast: str = ""    # optional middle tier


class AutomationConfig(BaseModel):
    # Event-driven auto-capture (see `torsor hooks install`). Capture behaviors
    # default ON: installing the hooks is itself the explicit opt-in, and each
    # only writes .torsor/ Markdown (the source of truth) or the disposable
    # index — never user code. The one behavior that could surprise by blocking
    # a push defaults OFF. Every hook-run core checks its flag and no-ops when
    # disabled, so a user can neuter any single behavior via torsor.toml without
    # uninstalling. torsor never calls an LLM and never runs a daemon — these
    # fire per-event (git / Claude Code lifecycle) and exit.
    auto_handoff: bool = True          # deterministic digest handoff on session end
    auto_map_on_commit: bool = True    # partial-map the just-committed files
    auto_snapshot_on_commit: bool = True  # refresh the complexity regression baseline
    guard_on_push: bool = False        # advisory pre-push guard — never surprise-blocks
    parse_transcript: bool = False     # opt-in transcript enrichment for auto-handoff


class TorsorConfig(BaseModel):
    version: int = 1
    budgets: BudgetConfig = Field(default_factory=BudgetConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    automation: AutomationConfig = Field(default_factory=AutomationConfig)


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
