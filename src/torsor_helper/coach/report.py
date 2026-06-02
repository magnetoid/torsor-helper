from __future__ import annotations

from torsor_helper import db
from torsor_helper.coach import health, hotspots, recommender
from torsor_helper.coach.state import CoachState
from torsor_helper.models import Recommendation
from torsor_helper.store import Store

_SEVERITY_RANK = {"important": 0, "suggest": 1, "info": 2}


def assemble(store: Store, config, context=None, limit: int = 8, conn=None, embedder=None) -> list[Recommendation]:
    modules_in_map: set[str] = set(db.modules(conn)) if conn is not None else set()

    recs: list[Recommendation] = health.run_health(store, modules_in_map)
    if conn is not None:  # hotspots need the indexed path; they self-skip outside a git repo
        recs += hotspots.find_hotspots(store.paths.root)
    if context:
        recs += recommender.best_practice_recs(store, config, context, conn=conn, embedder=embedder, limit=limit)

    state = CoachState(store.paths.index_dir / "coach_state.json")
    recs = [r for r in recs if not state.is_dismissed(r.key)]
    # Rank by severity, then decay (recs shown many times sink within their band
    # so the Coach never nags), then score, then key for a stable total order.
    recs.sort(key=lambda r: (_SEVERITY_RANK.get(r.severity, 1), state.times_shown(r.key), -r.score, r.key))
    recs = recs[:limit]

    for rec in recs:
        state.seen(rec.key)
    state.save()
    return recs


def session_digest(store: Store, limit: int = 3) -> list[Recommendation]:
    """Read-only hygiene digest for session start: the index-free checks
    (thin/stale/unruled), dismissal-filtered and severity-ranked. Does NOT
    record `seen` — a persistent unaddressed issue keeps surfacing every
    session until it's fixed or explicitly dismissed (no decay here)."""
    recs = health.check_thin(store) + health.check_stale(store) + health.check_unruled(store)
    state = CoachState(store.paths.index_dir / "coach_state.json")
    recs = [r for r in recs if not state.is_dismissed(r.key)]
    recs.sort(key=lambda r: (_SEVERITY_RANK.get(r.severity, 1), r.key))
    return recs[:limit]
