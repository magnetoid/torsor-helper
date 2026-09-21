from __future__ import annotations

import tomllib

import tomli_w
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal

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


class _Strict(BaseModel):
    """Reject unknown keys. Pydantic ignores them by default, so a typo'd section
    or field (`[automaton]`, `guard_on_edit = "blok"`) silently left the default
    in place while the user believed they had configured something."""

    model_config = ConfigDict(extra="forbid")


class BudgetConfig(_Strict):
    bootstrap_tokens: int = 2000
    recall_tokens: int = 1500
    # The SessionStart hook digest. Deliberately small: it lands in *every*
    # session (and again after each compaction) without the agent asking, so it
    # follows the "core tier under ~500 tokens" rule for injected context —
    # bootstrap_session() stays the fuller, on-demand form.
    session_start_tokens: int = 500
    # get_intent assembles architecture + decisions + symbols; it grows with the
    # ADR count, so it carries its own ceiling rather than borrowing bootstrap's.
    intent_tokens: int = 1200
    # A best-practice pack is static prose; with no language argument every
    # detected pack is concatenated, which is the largest single MCP response.
    practices_tokens: int = 1200
    # Default ceiling on list-shaped output (impact callers, decision titles,
    # verify reasons, drift/dep/staleness findings). What is hidden is always
    # counted in the response, so the agent knows the list is partial.
    max_items: int = 25
    # The rules digest and the primer are meant to be written into a prompt file
    # once, not fetched per session, so their ceilings are smaller than recall's.
    rules_tokens: int = 600
    primer_tokens: int = 800
    chars_per_token: int = 4


class EmbeddingConfig(_Strict):
    provider: str = "fastembed"
    model: str = "BAAI/bge-small-en-v1.5"
    dim: int = 384


class IndexConfig(_Strict):
    rrf_k: int = 60
    recency_weight: float = 0.1
    graph_boost: float = 0.1
    auto_index: bool = True
    mmr_lambda: float = 0.7  # MMR relevance/diversity trade-off (1.0 = pure relevance)
    importance_floors: dict[str, float] = Field(default_factory=lambda: dict(_DEFAULT_IMPORTANCE_FLOORS))

    @field_validator("importance_floors", mode="after")
    @classmethod
    def _upper_and_known(cls, value: dict[str, float]) -> dict[str, float]:
        """Keys are Tier names, which are uppercase. A user writing `active =
        0.85` got a silently ignored key and decay left off, so uppercase them
        — and reject a name that is not a tier, which can only be a typo."""
        out = dict(_DEFAULT_IMPORTANCE_FLOORS)
        for key, floor in value.items():
            name = str(key).upper()
            if name not in _DEFAULT_IMPORTANCE_FLOORS:
                raise ValueError(
                    f"unknown tier {key!r} in importance_floors; expected one of "
                    + ", ".join(sorted(_DEFAULT_IMPORTANCE_FLOORS))
                )
            out[name] = floor
        return out
    # Depth bound for `connect`: a dense graph would otherwise render a path no
    # one reads, and the search cost grows with it.
    connect_max_hops: int = 12


class ModelsConfig(_Strict):
    # Model-tier policy (token thrift). torsor never calls models — it publishes
    # this routing policy for the orchestrating agent/harness to follow.
    cheap: str = ""   # basic, deterministic work (torsor lookups, command replays)
    smart: str = ""   # thinking & construction (design, code, decisions)
    fast: str = ""    # optional middle tier


class AutomationConfig(_Strict):
    # Event-driven auto-capture (see `torsor hooks install`). Capture behaviors
    # default ON: installing the hooks is itself the explicit opt-in, and each
    # only writes .torsor/ Markdown (the source of truth) or the disposable
    # index — never user code. The one behavior that could surprise by blocking
    # a push defaults OFF. Every hook-run core checks its flag and no-ops when
    # disabled, so a user can neuter any single behavior via torsor.toml without
    # uninstalling. torsor never calls an LLM and never runs a daemon — these
    # fire per-event (git / Claude Code lifecycle) and exit.
    auto_bootstrap: bool = True        # inject a project digest at SessionStart (and after compaction)
    auto_handoff: bool = True          # deterministic digest handoff on session end
    auto_map_on_commit: bool = True    # partial-map the just-committed files
    auto_snapshot_on_commit: bool = True  # refresh the complexity regression baseline
    guard_on_push: bool = False        # advisory pre-push guard — never surprise-blocks
    # PreToolUse edit gate: check the *proposed* Edit/Write against ADR rules
    # before it lands. "advise" (default) only adds context — the guard stays
    # advisory (ADR 0009/0012); "block" denies on new severity=error drift;
    # "off" silences it without uninstalling.
    guard_on_edit: Literal["off", "advise", "block"] = "advise"
    parse_transcript: bool = False     # opt-in transcript enrichment for auto-handoff


class CoachConfig(_Strict):
    # How far back churn and temporal-coupling read. Unbounded, these walked the
    # entire history twice on every `torsor coach`, so the cost grew with the
    # repo's age forever — and a file that was hot three years ago is not the
    # signal either check is looking for. 0 means no bound.
    history_days: int = 365


class MemoryConfig(_Strict):
    # How journal files are named. "date" is one file per day, which two
    # branches both append to — fine, because `.torsor/.gitattributes` gives
    # journals a union merge. "date-author" gives each git identity its own
    # file, so concurrent work never touches the same path at all; use it when
    # the team is large enough that union merges get noisy. Changing it does
    # not rewrite existing journals — both shapes are read.
    journal_partition: Literal["date", "date-author"] = "date"


class CleanConfig(_Strict):
    # `torsor clean` retention. Journals are the only episodic tier that grows
    # unboundedly (one file per active day) and the only category clean can
    # discard that isn't re-derivable, so the window is explicit and tunable;
    # 0 disables journal expiry entirely. Everything else clean reclaims is
    # either orphaned (its source file is gone) or rebuildable from Markdown.
    journal_retention_days: int = 90


class TorsorConfig(_Strict):
    version: int = 1
    budgets: BudgetConfig = Field(default_factory=BudgetConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    automation: AutomationConfig = Field(default_factory=AutomationConfig)
    coach: CoachConfig = Field(default_factory=CoachConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    clean: CleanConfig = Field(default_factory=CleanConfig)


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
