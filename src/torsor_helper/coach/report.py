from __future__ import annotations

from torsor_helper import cartographer, db, deps
from torsor_helper.coach import (
    contradiction, coupling, health, hotspots, hubs, recommender, staleness, trend,
)
from torsor_helper.coach.state import CoachState
from torsor_helper.models import Recommendation
from torsor_helper.store import Store, state_file

_SEVERITY_RANK = {"important": 0, "suggest": 1, "info": 2}


def _coach_state_path(store):
    # store.state_file, not operations' — coach/ must not depend on operations.
    return state_file(store.paths, "coach_state.json")


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
    map_current: bool | None = None
    mapped_at_ns: int | None = None
    if conn is not None:
        stamp = db.meta_get(conn, "map_fingerprint")
        map_current = bool(stamp) and stamp == cartographer.repo_fingerprint(store.paths.root)
        raw = db.meta_get(conn, "mapped_at_ns")
        mapped_at_ns = int(raw) if raw and raw.isdigit() else None

    recs: list[Recommendation] = health.run_health(
        store, modules_in_map, map_current=map_current, mapped_at_ns=mapped_at_ns)
    # Only dangling wikilinks surface passively (deletion is unambiguous). Dead
    # path refs (check_path_refs) can still catch an example path, so they live
    # only in the explicit `torsor stale` command, not the always-on Coach.
    recs += staleness.check_dangling_links(store)
    recs += staleness.check_ambiguous_links(store)
    recs += contradiction.find_contradictions(store)
    if conn is not None:  # indexed path; these self-skip outside a git repo / on a clean project
        days = config.coach.history_days if config is not None else 365
        recs += hotspots.find_hotspots(store.paths.root, history_days=days)
        recs += _phantom_dep_recs(store)
        recs += coupling.find_coupling_recs(store.paths.root, conn, history_days=days)
        recs += hubs.find_hub_recs(conn)
        recs += trend.find_regressions(store.paths.root, conn)
    if context:
        recs += recommender.best_practice_recs(store, config, context, conn=conn, embedder=embedder, limit=limit)

    state = CoachState(_coach_state_path(store), clock=store.clock)
    recs = [r for r in recs if not state.is_dismissed(r.key)]

    # Resolution is computed against EVERYTHING produced this run, before the
    # page is truncated — otherwise raising `limit` would "fix" things and
    # lowering it would un-fix them.
    resolved = state.resolve_missing({r.key for r in recs} | {_RESOLVED_KEY})

    recs = [_escalate(r, state) for r in recs]
    # Rank by severity, then decay (recs shown many times sink within their band
    # so the Coach never nags), then score, then key for a stable total order.
    recs.sort(key=lambda r: (_SEVERITY_RANK.get(r.severity, 1), state.times_shown(r.key), -r.score, r.key))
    recs = recs[:limit]

    # Prepended AFTER the cut, and not counted against it. Ranked with the rest
    # it sorts into the info band and falls off any page with eight suggestions
    # on it — while resolve_missing has already dropped the state, so the good
    # news would be reported into a void and never come back. It is one line.
    if resolved:
        recs.insert(0, _resolved_rec(resolved))

    for rec in recs:
        state.seen(rec.key)
    state.save()
    return recs


_RESOLVED_KEY = "resolved"
# Long enough that a recommendation has genuinely been ignored rather than just
# seen twice in one afternoon, and paired with a day count so the escalation is
# information rather than pressure.
_ESCALATE_AFTER_SHOWS = 3
_ESCALATE_AFTER_DAYS = 7


def _resolved_rec(keys: list[str]) -> Recommendation:
    """What got fixed since last time, as one line.

    Its own key is excluded from resolution sweeps, or the regress is infinite:
    this rec is shown, is absent next run, and reports that the report was
    fixed — forever."""
    shown, tail = keys[:5], len(keys) - 5
    listed = ", ".join(shown) + (f" (+{tail} more)" if tail > 0 else "")
    return Recommendation(
        kind="resolved", severity="info",
        message=f"Fixed since last time: {listed}.",
        action="", source="", key=_RESOLVED_KEY,
        # Top of the info band: good news is cheap to read and stops the user
        # wondering where a recommendation went.
        score=1.0,
    )


def _escalate(rec: Recommendation, state: CoachState) -> Recommendation:
    """Say how long an important recommendation has been open.

    Deliberately adds information and NOT position. The decay above — recs shown
    many times sink within their band — is what keeps the Coach from nagging,
    and escalating by rank would quietly reverse it."""
    if rec.severity != "important" or rec.kind == _RESOLVED_KEY:
        return rec
    days = state.days_open(rec.key)
    if state.times_shown(rec.key) < _ESCALATE_AFTER_SHOWS or days < _ESCALATE_AFTER_DAYS:
        return rec
    return rec.model_copy(update={"message": f"{rec.message} (open {days} days)"})


def session_digest(store: Store, limit: int = 3) -> list[Recommendation]:
    """Read-only hygiene digest for session start: the index-free checks
    (thin/stale/unruled), dismissal-filtered and severity-ranked. Does NOT
    record `seen` — a persistent unaddressed issue keeps surfacing every
    session until it's fixed or explicitly dismissed (no decay here)."""
    # No resolution sweep here, deliberately: this runs three index-free checks,
    # so a key it does not produce is absent because it was not looked for, not
    # because it was solved. Claiming otherwise would mark every hotspot "fixed"
    # at the start of every session.
    recs = health.check_thin(store) + health.check_stale(store) + health.check_unruled(store)
    state = CoachState(_coach_state_path(store), clock=store.clock)
    recs = [r for r in recs if not state.is_dismissed(r.key)]
    recs.sort(key=lambda r: (_SEVERITY_RANK.get(r.severity, 1), r.key))
    return recs[:limit]
