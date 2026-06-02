from __future__ import annotations

from torsor_helper import db
from torsor_helper.models import Recommendation, Tier
from torsor_helper.search import hybrid_search
from torsor_helper.store import Store

# Map the tier of a recalled note to a best-practice recommendation kind.
_TIER_KIND = {Tier.ARCHITECTURE: "decision", Tier.EPISODIC: "learning"}


def best_practice_recs(store: Store, config, context, conn, embedder, limit: int = 5) -> list[Recommendation]:
    if conn is None or embedder is None or not context:
        return []
    out: list[Recommendation] = []

    # 1. Reuse: existing symbols that match the context (anti-duplication).
    for sym in db.search_symbols(conn, context, limit=3):
        out.append(Recommendation(
            kind="reuse", severity="suggest",
            message=f"`{sym.signature}` already exists in {sym.module}:{sym.line} — reuse it instead of reimplementing.",
            action=f"reuse {sym.name}", source=f"{sym.module}:{sym.line}",
            key=f"reuse:{sym.module}:{sym.name}", score=float(sym.refs),
        ))

    # 2. Relevant prior decisions / learnings from memory.
    result = hybrid_search(conn, embedder, config, context, limit=limit)
    for hit in result.hits:
        if not hit.path:  # skip the budget-omitted sentinel marker
            continue
        kind = _TIER_KIND.get(hit.tier)
        if kind is None:
            continue
        verb = "decided" if kind == "decision" else "learned"
        out.append(Recommendation(
            kind=kind, severity="info",
            message=f"You previously {verb} something relevant: {hit.title} — {hit.snippet[:120]}",
            action=f"review {hit.path}", source=hit.path,
            key=f"{kind}:{hit.path}", score=hit.score,
        ))
    return out
