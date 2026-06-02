from __future__ import annotations

import re

from torsor_helper import db
from torsor_helper.budget import estimate_tokens
from torsor_helper.models import RecallHit, RecallResult, Tier
from torsor_helper.snippets import best_snippet

_WORD = re.compile(r"\w+")
_TIER_WEIGHTS = {
    Tier.CHARTER: 1.5, Tier.ARCHITECTURE: 1.4, Tier.ACTIVE: 1.2, Tier.MAP: 1.1, Tier.EPISODIC: 1.0,
}


def hybrid_search(conn, embedder, config, query, *, limit=8, max_tokens=1500, type_=None, kind=None) -> RecallResult:
    terms = [t for t in _WORD.findall(query.lower()) if t]
    if not terms:
        return RecallResult(query=query, hits=[], total_tokens=0)

    k = config.index.rrf_k
    pool = max(limit * 4, 20)
    qvec = embedder.embed([query])[0]
    vec_ranked = db.cosine_search(conn, qvec, pool)
    fts_ranked = db.fts_search(conn, query, pool)

    scores: dict[str, float] = {}
    for rank, (path, _) in enumerate(vec_ranked):
        scores[path] = scores.get(path, 0.0) + 1.0 / (k + rank)
    for rank, (path, _) in enumerate(fts_ranked):
        scores[path] = scores.get(path, 0.0) + 1.0 / (k + rank)
    if not scores:
        return RecallResult(query=query, hits=[], total_tokens=0)

    rows = {p: db.note_row(conn, p) for p in scores}
    by_recency = sorted(scores, key=lambda p: (rows[p] or {}).get("updated") or "", reverse=True)
    for rank, path in enumerate(by_recency):
        scores[path] += config.index.recency_weight * (1.0 / (k + rank))

    top = max(scores, key=lambda p: scores[p])
    for nbr in db.neighbors(conn, top):
        if nbr in scores:
            scores[nbr] += config.index.graph_boost * (1.0 / k)

    hits: list[RecallHit] = []
    for path, score in scores.items():
        row = rows.get(path)
        if row is None:
            continue
        if type_ is not None and row["type"] != type_:
            continue
        if kind is not None and row["kind"] != kind:
            continue
        tier = Tier(row["tier"])
        hits.append(RecallHit(
            path=path, title=row["title"] or path, tier=tier,
            score=score * _TIER_WEIGHTS.get(tier, 1.0),
            snippet=best_snippet(db.body_of(conn, path), terms),
        ))

    hits.sort(key=lambda h: (-h.score, h.path))

    selected: list[RecallHit] = []
    used = 0
    cpt = config.budgets.chars_per_token
    for hit in hits[:limit]:
        cost = estimate_tokens(hit.snippet, cpt)
        if selected and used + cost > max_tokens:
            break
        selected.append(hit)
        used += cost

    db.bump_access(conn, [h.path for h in selected])
    return RecallResult(query=query, hits=selected, total_tokens=used)
