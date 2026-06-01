from __future__ import annotations

from enum import Enum, IntEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Tier(IntEnum):
    CHARTER = 0
    ARCHITECTURE = 1
    MAP = 2
    ACTIVE = 3
    EPISODIC = 4


class MemoryKind(str, Enum):
    OBSERVATION = "observation"
    DECISION = "decision"
    LEARNING = "learning"
    BLOCKER = "blocker"
    HANDOFF = "handoff"


class Frontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    status: str = "active"
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    created: str | None = None
    updated: str | None = None


class Note(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    tier: Tier
    frontmatter: Frontmatter
    title: str
    body: str
    content_hash: str


class RecallHit(BaseModel):
    path: str
    title: str
    tier: Tier
    score: float
    snippet: str


class RecallResult(BaseModel):
    query: str
    hits: list[RecallHit] = Field(default_factory=list)
    total_tokens: int = 0
