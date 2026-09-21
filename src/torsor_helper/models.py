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
    # Project Markdown outside .torsor/ (README, docs/) — indexed in place,
    # never written. Last, so every stored tier integer keeps its meaning.
    DOCS = 5


# Canonical per-tier recall weight. The single source of truth for both the
# indexed search path (search.py) and the keyword fallback (recall.py) — keep
# it here so the two rankings can never silently diverge.
TIER_WEIGHTS: dict[Tier, float] = {
    Tier.CHARTER: 1.5,
    Tier.ARCHITECTURE: 1.4,
    # Authored by the project, so above working notes and the derived map; not
    # curated as intent, so below the charter and architecture.
    Tier.DOCS: 1.3,
    Tier.ACTIVE: 1.2,
    Tier.MAP: 1.1,
    Tier.EPISODIC: 1.0,
}

# Applied on top of the MAP weight to a map note for test code. Test names are
# prose about behaviour (test_webhook_routes_message), so lexically they look
# like answers to natural-language questions and outrank the code they test —
# on a real project, 2 to 4 of the top 5 recall slots for 7 of 7 questions.
# Weighted down rather than removed: a question that names a test still finds it.
TEST_MAP_WEIGHT = 0.5


def recall_weight(tier: Tier, title: str) -> float:
    """The tier weight, adjusted for a map note that documents test code."""
    from torsor_helper.paths import is_test_path

    weight = TIER_WEIGHTS.get(tier, 1.0)
    if tier is Tier.MAP and is_test_path(title):
        weight *= TEST_MAP_WEIGHT
    return weight


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
    # Declared, not merely allowed: `kind` is an indexed column and a search
    # filter, and `rules` is what the guard enforces. Leaving them to
    # extra="allow" meant their types were never checked at all.
    kind: str | None = None
    rules: list[dict] = Field(default_factory=list)


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
    kind: str  # "function" | "class" | "method" | "type"
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
    # Module the name resolves to, or None if best-effort failed. ALWAYS the
    # canonical dotted key produced by the extractor/resolver (norm_module
    # already applied) — consumers must never re-normalize it, only compare it
    # against another canonical key (e.g. norm_module(sym.module) for a symbol's
    # own file path).
    resolved_module: str | None = None
    # Language-specific resolution hint (e.g. the Go import path a `pkg.Fn` call
    # was qualified by). PERSISTED (schema 7): the Go cross-file resolver branches
    # on it, so an edge that lost its hint on the DB round-trip would look like a
    # bare same-package call and resolve to the wrong symbol on a partial remap.
    hint: str | None = None


class Rule(BaseModel):
    # kind: forbid_import | forbid_pattern | require_import | forbid_layer_import
    #     | forbid_cycle (graph-wide: needs the symbol map, not one file's source)
    kind: str
    target: str          # module prefix (forbid/require_import), or regex (forbid_pattern/forbid_layer_import)
    # Path-aware glob over the posix relpath (guard.scope_matches): `*` and `?`
    # stay inside one segment, `**` spans directories, and a pattern with no
    # "/" matches at any depth the way a .gitignore pattern does.
    scope: str = "*.py"
    # "everywhere in scope, except here". A rule without one is unchanged; a
    # rule that needs one otherwise has to choose between lying and forbidding
    # something legitimate — ADR 0002 forbids importing the CLI, which is right
    # for every core module and wrong for the __main__ that has to.
    exclude: str = ""
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
    # kind: thin | stale | unruled | uncharted | uncharted_language | reuse | decision | learning
    #       | hotspot | phantom_dep | coupling | hub | regression | dangling_link | stale_path
    #       | ambiguous_link | contradiction | resolved
    # `resolved` is the odd one: it reports what STOPPED being recommended, so it
    # is good news rather than work, and coach/report excludes its own key from
    # the resolution sweep or it reports itself forever.
    kind: str
    severity: str = "suggest"  # info | suggest | important
    message: str
    action: str = ""
    source: str = ""
    key: str           # stable id for dedup / dismissal / decay
    score: float = 0.0
