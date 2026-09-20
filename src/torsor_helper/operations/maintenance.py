"""Housekeeping: the Coach, staleness marking, the garbage collector, and the
consolidation pass that mines journals into insight notes.

All advisory. Nothing here edits source code, and the only writes are to
torsor's own derived artefacts or to a note's frontmatter `status`."""
from __future__ import annotations

from torsor_helper import cleaner, db
from torsor_helper.coach import mining as coach_mining
from torsor_helper.coach import report as coach_report
from torsor_helper.coach import staleness as _staleness
from torsor_helper.coach import trend as coach_trend
from torsor_helper.coach.state import CoachState
from torsor_helper.indexer import reindex
from torsor_helper.models import Frontmatter
from torsor_helper.operations._shared import _embedder_for, _log_op, _open_index
from torsor_helper.operations._state import _coach_state_path
from torsor_helper.paths import contained


def recommend(store, config, context=None, limit=8):
    conn = _open_index(store, config)
    embedder = _embedder_for(config) if conn is not None else None
    try:
        return coach_report.assemble(store, config, context=context, limit=limit, conn=conn, embedder=embedder)
    finally:
        if conn is not None:
            conn.close()

def dismiss_recommendation(store, key) -> None:
    state = CoachState(_coach_state_path(store))
    state.dismiss(key)
    state.save()

def check_staleness(store, config, *, mark=False, unmark=False) -> dict:
    """Detect memory that contradicts current code — dangling [[wikilinks]] and
    dead file-path references (deterministic, index-free, high-precision). Read-only
    by default; `--mark` sets `status: stale` on the offending notes (opt-in,
    reversible via `--unmark`), never touching the note body (ADR 0010)."""
    _log_op(store, "check_staleness", "")
    findings = _staleness.run_staleness(store)
    counts: dict[str, int] = {}
    for r in findings:
        counts[r.kind] = counts.get(r.kind, 0) + 1

    marked: list[str] = []
    if unmark:
        marked = _set_note_status(store, sorted({_note_rel(store, p) for p in _stale_notes(store)}), "active")
    elif mark:
        marked = _set_note_status(store, sorted({r.source for r in findings}), "stale")
    return {"findings": findings, "counts": counts, "marked": marked}

def _stale_notes(store):
    for path in store.iter_note_paths():
        try:
            if store.read_note(path).frontmatter.status == "stale":
                yield path
        except (OSError, UnicodeDecodeError):
            continue

def _note_rel(store, path) -> str:
    try:
        return path.relative_to(store.paths.root).as_posix()
    except ValueError:
        return str(path)

def _set_note_status(store, rels: list[str], status: str) -> list[str]:
    """Rewrite each note's frontmatter `status`, preserving body + other fields
    (mirrors the record_decision supersede rewrite). Returns the notes changed."""
    changed: list[str] = []
    for rel in rels:
        path = contained(store.paths.root, rel)
        if path is None or not path.exists():
            continue  # a finding's source must name a note inside the project
        note = store.read_note(path)
        if note.frontmatter.status == status:
            continue
        data = note.frontmatter.model_dump(exclude_none=True)
        data["status"] = status
        store.write_note(path, Frontmatter.model_validate(data), note.title, note.body)
        changed.append(rel)
    return changed

def clean(store, config, *, apply: bool = False, deep: bool = False) -> dict:
    """Reclaim derived and expired torsor artefacts. Dry-run by default: without
    `apply` nothing is touched and the returned stats describe what *would* go.
    Never removes a stable tier (charter/architecture/active/insights) or any
    source file — `cleaner` only ever targets orphaned map notes, dead index
    rows, journals past the retention window, and (with `deep`) the whole index."""
    _log_op(store, "clean", f"apply={apply} deep={deep}")
    proposed = cleaner.plan(store, config, deep=deep)
    stats = {
        "dry_run": not apply,
        "map_orphans": len(proposed.map_orphans),
        "journals_expired": len(proposed.journal_expired),
        "dead_rows": sum(proposed.dead_rows.values()),
        "deep": bool(proposed.deep_paths),
        "reclaimed_bytes": proposed.reclaimed_bytes,
        "insights_mined": 0,
        "notes": list(proposed.notes),
        "files": [str(p.relative_to(store.paths.root)) for p in proposed.files],
    }
    if apply:
        stats.update(cleaner.apply(store, config, proposed))
        stats["dry_run"] = False
    return stats

def consolidate(store, config) -> dict:
    written = coach_mining.mine_insights(store)
    duplicates = coach_mining.find_duplicate_entries(store)

    # consolidate is a maintenance pass: index once, directly, so the `indexed`
    # count reflects the freshly-mined insights. (Using _open_index here would
    # reindex internally first, leaving this explicit call to report 0.)
    conn = db.connect(store.paths.index_db)
    try:
        indexed = reindex(store, conn, _embedder_for(config))["indexed"]
        top_accessed = db.top_accessed(conn, limit=3)
    finally:
        conn.close()

    # Snapshot complexity so the Coach can report regressions *since this pass*.
    _snapshot_complexity(store)

    return {
        "insights": len(written),
        "duplicates": len(duplicates),
        "indexed": indexed,
        "top_accessed": top_accessed,
    }

def _snapshot_complexity(store) -> None:
    """Refresh the per-file complexity baseline `coach/trend.find_regressions`
    diffs against. Shared by `consolidate` and the post-commit auto-capture hook,
    so a regression baseline stays fresh with zero manual maintenance calls."""
    if not store.paths.index_db.exists():
        return
    conn = db.connect(store.paths.index_db)
    try:
        db.save_complexity_snapshot(conn, coach_trend.current_complexity(store.paths.root))
    finally:
        conn.close()
