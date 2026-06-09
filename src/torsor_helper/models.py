from __future__ import annotations

from enum import Enum, IntEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Tier(IntEnum):
    # NOTE: CHARTER == 0 is falsy. Never test a tier with truthiness
    # (`if note.tier:`); always compare explicitly (`is`, `==`, `.get(tier)`).
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
    score: float = Field(ge=0.0)  # raw count * tier weight; unbounded above
    snippet: str


class RecallResult(BaseModel):
    query: str
    hits: list[RecallHit] = Field(default_factory=list)
    total_tokens: int = 0


class Symbol(BaseModel):
    name: str
    kind: str  # "function" | "class" | "method"
    signature: str
    module: str
    line: int
    doc: str = ""
    refs: int = 0  # count of *resolved* references (AST edges), not substring hits


class SymbolEdge(BaseModel):
    caller: str             # enclosing symbol that makes the reference ("<module>" for top level)
    referenced_name: str    # the referenced name (call target / read / write)
    role: str               # "call" | "read" | "write"
    module: str             # module (relpath) the reference lives in
    resolved_module: str | None = None  # module the name resolves to, or None if best-effort failed


class Rule(BaseModel):
    # kind: forbid_import | forbid_pattern | require_import | forbid_layer_import
    kind: str
    target: str          # module prefix (forbid/require_import), or regex (forbid_pattern/forbid_layer_import)
    scope: str = "*.py"  # fnmatch glob over the posix path, relative to the repo root
    message: str = ""
    source: str = ""     # ADR/title that declared this rule (for citation)
    severity: str = "warning"  # hint | info | warning | error
    rule_id: str = ""    # stable id; defaults to f"{kind}:{target}"


class Violation(BaseModel):
    rule_kind: str
    target: str
    file: str
    line: int = 0
    message: str
    source: str
    severity: str = "warning"
    rule_id: str = ""


class Recommendation(BaseModel):
    # kind: thin | stale | unruled | uncharted | reuse | decision | learning | hotspot
    #       | phantom_dep | coupling | regression
    kind: str
    severity: str = "suggest"  # info | suggest | important
    message: str
    action: str = ""
    source: str = ""
    key: str           # stable id for dedup / dismissal / decay
    score: float = 0.0
