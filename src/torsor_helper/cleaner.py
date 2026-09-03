from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from torsor_helper import db


@dataclass
class CleanPlan:
    """What a clean pass *would* reclaim. Building one never touches disk."""

    map_orphans: list[Path] = field(default_factory=list)
    dead_rows: dict[str, int] = field(default_factory=dict)
    journal_expired: list[Path] = field(default_factory=list)
    deep_paths: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def files(self) -> list[Path]:
        return [*self.map_orphans, *self.journal_expired, *self.deep_paths]

    @property
    def reclaimed_bytes(self) -> int:
        """Bytes the listed files occupy. Dead index rows are excluded — what
        VACUUM actually returns isn't knowable before it runs."""
        return sum(_size(p) for p in self.files)

    @property
    def is_empty(self) -> bool:
        return not self.files and not any(self.dead_rows.values())


def _size(path: Path) -> int:
    if path.is_dir():
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _map_note_name(module: str) -> str:
    """The map-note filename cartographer.render_map writes for `module` —
    the same mangling, applied forward, so we never reverse-parse a filename
    (which is ambiguous for modules containing '__', e.g. '__init__.py')."""
    return f"{module.replace('/', '__')}.md"


def _live_map_notes(store) -> set[str]:
    """Map-note filenames for indexed modules whose source file still exists."""
    conn = db.connect(store.paths.index_db)
    try:
        modules = db.modules(conn)
    finally:
        conn.close()
    return {_map_note_name(m) for m in modules if (store.paths.root / m).exists()}


def _plan_map_orphans(store, out: CleanPlan) -> None:
    modules_dir = store.paths.map_dir / "modules"
    if not modules_dir.is_dir():
        return
    if not store.paths.index_db.exists():
        out.notes.append("map: skipped (no index — run `torsor map` first)")
        return
    live = _live_map_notes(store)
    out.map_orphans = sorted(p for p in modules_dir.glob("*.md") if p.name not in live)


# Index tables keyed by a repo-relative source path. A row whose file no longer
# exists is dead weight: `map` replaces symbols/edges wholesale only when it is
# re-run, and nothing ever prunes path_access or complexity_snapshot.
_PATH_COLUMNS = {
    "symbols": "module",
    "symbol_edges": "module",
    "complexity_snapshot": "file",
    "path_access": "path",
}


def _dead_rows(store, conn) -> dict[str, int]:
    root = store.paths.root
    counts: dict[str, int] = {}
    for table, column in _PATH_COLUMNS.items():
        dead = sum(
            row[0]
            for row in conn.execute(f"SELECT COUNT(*), {column} FROM {table} GROUP BY {column}")
            if row[1] and not (root / row[1]).exists()
        )
        counts[table] = dead
    return counts


def _plan_journal_expiry(store, config, out: CleanPlan) -> None:
    days = config.clean.journal_retention_days
    if days <= 0:
        out.notes.append("journal: retention disabled (clean.journal_retention_days = 0)")
        return
    if not store.paths.journal_dir.is_dir():
        return
    cutoff = store.clock().date() - timedelta(days=days)
    expired = []
    for path in sorted(store.paths.journal_dir.glob("*.md")):
        try:
            stamp = date.fromisoformat(path.stem)
        except ValueError:
            continue  # not a dated journal file — never ours to expire
        if stamp < cutoff:
            expired.append(path)
    out.journal_expired = expired


def plan(store, config, *, deep: bool = False) -> CleanPlan:
    """Compute what a clean pass would reclaim. Strictly read-only: this is the
    dry run, and callers render it before anyone opts into `apply`."""
    out = CleanPlan()
    _plan_journal_expiry(store, config, out)
    _plan_map_orphans(store, out)
    if deep:
        # The whole index goes, so per-row accounting is moot.
        if store.paths.index_dir.is_dir():
            out.deep_paths = [store.paths.index_dir]
        out.notes.append("deep: the index is rebuilt on the next `torsor index` / `torsor map`")
    elif store.paths.index_db.exists():
        conn = db.connect(store.paths.index_db)
        try:
            out.dead_rows = _dead_rows(store, conn)
        finally:
            conn.close()
    return out


def _purge_dead_rows(store, conn) -> int:
    root = store.paths.root
    removed = 0
    for table, column in _PATH_COLUMNS.items():
        values = [r[0] for r in conn.execute(f"SELECT DISTINCT {column} FROM {table}")]
        dead = [v for v in values if v and not (root / v).exists()]
        for value in dead:
            removed += conn.execute(f"DELETE FROM {table} WHERE {column}=?", (value,)).rowcount
    conn.commit()
    return removed


def apply(store, config, plan: CleanPlan) -> dict:
    """Execute `plan`. Only ever removes derived or expired artefacts — never a
    stable tier (charter/architecture/active/insights), never source code."""
    from torsor_helper.coach import mining

    reclaimed = plan.reclaimed_bytes

    # Mine BEFORE discarding: every learning/decision/rejection/blocker in an
    # expiring journal must already be durable in memory/insights/.
    mined = 0
    if plan.journal_expired:
        mined = len(mining.mine_insights(store))
    for path in plan.journal_expired:
        path.unlink(missing_ok=True)

    for path in plan.map_orphans:
        path.unlink(missing_ok=True)

    rows = 0
    if plan.deep_paths:
        for path in plan.deep_paths:
            shutil.rmtree(path, ignore_errors=True)
    elif store.paths.index_db.exists() and any(plan.dead_rows.values()):
        conn = db.connect(store.paths.index_db)
        try:
            rows = _purge_dead_rows(store, conn)
            reclaimed += _vacuum(conn, store.paths.index_db)
        finally:
            conn.close()

    return {
        "map_orphans": len(plan.map_orphans),
        "journals_expired": len(plan.journal_expired),
        "insights_mined": mined,
        "dead_rows": rows,
        "deep": bool(plan.deep_paths),
        "reclaimed_bytes": reclaimed,
    }


def _vacuum(conn, db_path: Path) -> int:
    """VACUUM the index and report the bytes it actually gave back."""
    before = _size(db_path)
    conn.execute("VACUUM")
    conn.commit()
    return max(0, before - _size(db_path))
