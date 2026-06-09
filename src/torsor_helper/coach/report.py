from __future__ import annotations

from torsor_helper import cartographer, db, deps
from torsor_helper.coach import coupling, health, hotspots, recommender, trend
from torsor_helper.coach.state import CoachState
from torsor_helper.models import Recommendation
from torsor_helper.store import Store

_SEVERITY_RANK = {"important": 0, "suggest": 1, "info": 2}


def _phantom_dep_recs(store: Store) -> list[Recommendation]:
    """Advisory: imports across the repo that resolve to no known package."""
    files = [p.relative_to(store.paths.root).as_posix() for p in cartographer.iter_source_files(store.paths.root)]
    out: list[Recommendation] = []
    for f in deps.unknown_imports(store.paths.root, files):
        out.append(Recommendation(
            kind="phantom_dep", severity="info",
            message=(
                f"{f['file']}:{f['line']} imports '{f['name']}', which resolves to no stdlib, "
                f"installed, first-party, or declared package — possible hallucinated dependency; "
                f"verify it exists before installing."
            ),
            action=f"verify package {f['name']}", source=f["file"],
            key=f"phantom_dep:{f['file']}:{f['name']}", score=0.0,
        ))
    return out


def assemble(store: Store, config, context=None, limit: int = 8, conn=None, embedder=None) -> list[Recommendation]:
    modules_in_map: set[str] = set(db.modules(conn)) if conn is not None else set()

    recs: list[Recommendation] = health.run_health(store, modules_in_map)
    if conn is not None:  # indexed path; these self-skip outside a git repo / on a clean project
        recs += hotspots.find_hotspots(store.paths.root)
        recs += _phantom_dep_recs(store)
        recs += coupling.find_coupling_recs(store.paths.root, conn)
        recs += trend.find_regressions(store.paths.root, conn)
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
