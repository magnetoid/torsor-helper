from __future__ import annotations

import math
import re

import numpy as np

from torsor_helper import db
from torsor_helper.budget import hit_cost
from torsor_helper.indexer import _embedder_identity
from torsor_helper.models import TIER_WEIGHTS, RecallHit, RecallResult, Tier
from torsor_helper.snippets import best_snippet

_WORD = re.compile(r"\w+")
# Aliased for local readability; the object is the canonical one in models.py.
_TIER_WEIGHTS = TIER_WEIGHTS


def _importance(tier: Tier, access_count: int, floors: dict[str, float]) -> float:
    """Recall-frequency multiplier in [floor, 1.0]. access_count=0 → floor (no
    cold-start suppression); rises monotonically toward 1.0 as a note proves
    useful. Deterministic — a pure function of the stored counter, no clock."""
    floor = floors.get(tier.name, 1.0)
    if floor >= 1.0:
        return 1.0
    return floor + (1.0 - floor) * (1.0 - 1.0 / (1.0 + math.log1p(max(0, access_count))))


def _unit_vectors(vec_by_path):
    """Pre-normalize once. Cosine between unit vectors is a plain dot product,
    and MMR compares every remaining hit against every selected one — the norms
    were being recomputed on each of those pairs."""
    out = {}
    for path, v in vec_by_path.items():
        n = float(np.linalg.norm(v))
        if n > 0.0:
            out[path] = v / n
    return out


def _mmr_order(hits, vec_by_path, lam: float):
    """Reorder relevance-sorted hits by Maximal Marginal Relevance so near-
    duplicate notes don't crowd out distinct ones. mmr = λ·rel − (1−λ)·maxSim.
    No-ops (returns the input order) when fewer than 2 hits have vectors, so the
    keyword/hashing paths are untouched. Deterministic."""
    unit = _unit_vectors(vec_by_path)
    if sum(1 for h in hits if h.path in unit) < 2:
        return list(hits)
    max_score = max((h.score for h in hits), default=1.0) or 1.0
    remaining = list(hits)
    selected = [remaining.pop(0)]  # seed with the most relevant
    while remaining:
        best_i, best_val = 0, None
        for i, h in enumerate(remaining):
            rel = h.score / max_score
            v = unit.get(h.path)
            sim = 0.0
            if v is not None:
                sims = [float(np.dot(v, unit[s.path])) for s in selected
                        if s.path in unit and unit[s.path].shape == v.shape]
                sim = max(sims) if sims else 0.0
            val = lam * rel - (1.0 - lam) * sim
            if best_val is None or val > best_val:
                best_val, best_i = val, i
        selected.append(remaining.pop(best_i))
    return selected


def hybrid_search(conn, embedder, config, query, *, limit=8, max_tokens=1500, type_=None,
                  kind=None, include_superseded=False, symbol=None) -> RecallResult:
    terms = [t for t in _WORD.findall(query.lower()) if t]
    if not terms:
        return RecallResult(query=query, hits=[], total_tokens=0)

    k = config.index.rrf_k
    pool = max(limit * 4, 20)
    # Notes naming this symbol in backticks (store.extract_symbol_mentions).
    # An empty set is a real answer — nothing recorded about it — so it must be
    # distinguishable from "no filter asked for".
    mentioning = set(db.notes_mentioning(conn, symbol)) if symbol else None
    if type_ is not None or kind is not None or symbol is not None:
        # Filters are applied after RRF fusion; with a selective filter, matches
        # ranked below the unfiltered top pool would be unreachable (empty result
        # despite good matches). Widen the candidate pool to the whole corpus.
        pool = max(pool, db.note_count(conn))
    # Only fuse the vector leg when the stored vectors came from this run's
    # embedder. Across spaces the similarities are noise, not a weaker signal,
    # so RRF would rank on them just as confidently.
    if db.vectors_match(conn, _embedder_identity(embedder)):
        vec_ranked = db.cosine_search(conn, embedder.embed([query])[0], pool)
    else:
        vec_ranked = []
    fts_ranked = db.fts_search(conn, query, pool)

    if embedder.name == "hashing" and vec_ranked:
        # The fallback embedder hashes a bag of words into 384 buckets, so every
        # query has some similarity to every note. Left to fuse freely it
        # *created* hits: a query for something the project never recorded came
        # back with the charter, and recall could never answer "nothing here".
        # So the fallback ranks what the lexical side already found a basis for
        # and adds nothing. A real embedder introducing a hit with no lexical
        # overlap is exactly what semantic search is for, and is untouched.
        lexical = {path for path, _ in fts_ranked}
        vec_ranked = [pair for pair in vec_ranked if pair[0] in lexical]

    scores: dict[str, float] = {}
    for rank, (path, _) in enumerate(vec_ranked):
        scores[path] = scores.get(path, 0.0) + 1.0 / (k + rank)
    for rank, (path, _) in enumerate(fts_ranked):
        scores[path] = scores.get(path, 0.0) + 1.0 / (k + rank)
    if not scores:
        return RecallResult(query=query, hits=[], total_tokens=0)

    rows = db.note_rows(conn, scores)
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
        if mentioning is not None and path not in mentioning:
            continue
        # superseded decisions are stale intent — drop them unless explicitly asked
        if not include_superseded and row["type"] == "decision" and row["status"] == "superseded":
            continue
        tier = Tier(row["tier"])
        importance = _importance(tier, row["access_count"] or 0, config.index.importance_floors)
        hits.append(RecallHit(
            path=path, title=row["title"] or path, tier=tier,
            score=score * _TIER_WEIGHTS.get(tier, 1.0) * importance,
            snippet="",  # filled in below, for the survivors only
        ))

    # Score desc; ties broken toward the more stable tier (lower value), then path,
    # so scarce budget buys durable intent first.
    hits.sort(key=lambda h: (-h.score, h.tier.value, h.path))

    # Diversify: demote near-duplicate notes via MMR over the stored vectors.
    # MMR is quadratic in what it is given and only `limit` items survive it, so
    # it runs over a shortlist. 4x leaves room to demote near-duplicates without
    # paying for the long tail of a corpus-wide filter.
    pool = hits[: max(limit * 4, limit)]
    vec_by_path = db.get_vectors(conn, [h.path for h in pool])
    ordered = _mmr_order(pool, vec_by_path, config.index.mmr_lambda)

    # Only now compute snippets: each is an FTS lookup plus a scan of the body,
    # and doing it for every candidate before the cut was most of the search.
    candidates = [
        h.model_copy(update={"snippet": best_snippet(db.body_of(conn, h.path), terms)})
        for h in ordered[:limit]
    ]
    selected: list[RecallHit] = []
    used = 0
    truncated = False
    cpt = config.budgets.chars_per_token
    for hit in candidates:
        cost = hit_cost(hit.title, hit.snippet, cpt)
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
