from __future__ import annotations

import math
import re

import numpy as np

from torsor_helper import db
from torsor_helper.budget import estimate_tokens
from torsor_helper.models import RecallHit, RecallResult, Tier
from torsor_helper.snippets import best_snippet

_WORD = re.compile(r"\w+")
_TIER_WEIGHTS = {
    Tier.CHARTER: 1.5, Tier.ARCHITECTURE: 1.4, Tier.ACTIVE: 1.2, Tier.MAP: 1.1, Tier.EPISODIC: 1.0,
}


def _importance(tier: Tier, access_count: int, floors: dict[str, float]) -> float:
    """Recall-frequency multiplier in [floor, 1.0]. access_count=0 → floor (no
    cold-start suppression); rises monotonically toward 1.0 as a note proves
    useful. Deterministic — a pure function of the stored counter, no clock."""
    floor = floors.get(tier.name, 1.0)
    if floor >= 1.0:
        return 1.0
    return floor + (1.0 - floor) * (1.0 - 1.0 / (1.0 + math.log1p(max(0, access_count))))


def _cos(a, b) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0 or a.shape != b.shape:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _mmr_order(hits, vec_by_path, lam: float):
    """Reorder relevance-sorted hits by Maximal Marginal Relevance so near-
    duplicate notes don't crowd out distinct ones. mmr = λ·rel − (1−λ)·maxSim.
    No-ops (returns the input order) when fewer than 2 hits have vectors, so the
    keyword/hashing paths are untouched. Deterministic."""
    if sum(1 for h in hits if h.path in vec_by_path) < 2:
        return list(hits)
    max_score = max((h.score for h in hits), default=1.0) or 1.0
    remaining = list(hits)
    selected = [remaining.pop(0)]  # seed with the most relevant
    while remaining:
        best_i, best_val = 0, None
        for i, h in enumerate(remaining):
            rel = h.score / max_score
            v = vec_by_path.get(h.path)
            sim = 0.0
            if v is not None:
                sims = [_cos(v, vec_by_path[s.path]) for s in selected if s.path in vec_by_path]
                sim = max(sims) if sims else 0.0
            val = lam * rel - (1.0 - lam) * sim
            if best_val is None or val > best_val:
                best_val, best_i = val, i
        selected.append(remaining.pop(best_i))
    return selected


def hybrid_search(conn, embedder, config, query, *, limit=8, max_tokens=1500, type_=None, kind=None, include_superseded=False) -> RecallResult:
    terms = [t for t in _WORD.findall(query.lower()) if t]
    if not terms:
        return RecallResult(query=query, hits=[], total_tokens=0)

    k = config.index.rrf_k
    pool = max(limit * 4, 20)
    if type_ is not None or kind is not None:
        # Filters are applied after RRF fusion; with a selective filter, matches
        # ranked below the unfiltered top pool would be unreachable (empty result
        # despite good matches). Widen the candidate pool to the whole corpus.
        pool = max(pool, db.note_count(conn))
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
        # superseded decisions are stale intent — drop them unless explicitly asked
        if not include_superseded and row["type"] == "decision" and row["status"] == "superseded":
            continue
        tier = Tier(row["tier"])
        importance = _importance(tier, row["access_count"] or 0, config.index.importance_floors)
        hits.append(RecallHit(
            path=path, title=row["title"] or path, tier=tier,
            score=score * _TIER_WEIGHTS.get(tier, 1.0) * importance,
            snippet=best_snippet(db.body_of(conn, path), terms),
        ))

    # Score desc; ties broken toward the more stable tier (lower value), then path,
    # so scarce budget buys durable intent first.
    hits.sort(key=lambda h: (-h.score, h.tier.value, h.path))

    # Diversify: demote near-duplicate notes via MMR over the stored vectors.
    vec_by_path = db.get_vectors(conn, [h.path for h in hits])
    ordered = _mmr_order(hits, vec_by_path, config.index.mmr_lambda)

    candidates = ordered[:limit]
    selected: list[RecallHit] = []
    used = 0
    truncated = False
    cpt = config.budgets.chars_per_token
    for hit in candidates:
        cost = estimate_tokens(hit.snippet, cpt)
        if selected and used + cost > max_tokens:
            truncated = True
            break
        selected.append(hit)
        used += cost

    db.bump_access(conn, [h.path for h in selected])

    out = list(selected)
    if truncated:
        # count against the full relevant pool (not the limit-capped candidates)
        # so the number isn't misleadingly small
        dropped = len(hits) - len(selected)
        out.append(RecallHit(
            path="", title=f"… {dropped} more omitted (budget/limit)",
            tier=Tier.EPISODIC, score=0.0, snippet="",
        ))
    return RecallResult(query=query, hits=out, total_tokens=used)
