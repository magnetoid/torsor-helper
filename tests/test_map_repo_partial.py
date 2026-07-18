"""Partial `map_repo(paths=[...])` must merge the rescanned modules into the
existing symbol graph, not replace it wholesale (audit I-4). Before the fix,
`replace_all_*` deleted every module's symbols and re-inserted only the scanned
subset, so one-file remaps silently wiped the rest of the index."""
from datetime import datetime

from torsor_helper import db, operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _project(tmp_path):
    # app.py calls format_date from pkg/dates.py — a resolvable cross-module ref
    # (see test_cartographer_edges), so format_date.refs == 1 after a full map.
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "dates.py").write_text("def format_date(d):\n    return d\n")
    (tmp_path / "app.py").write_text(
        "from pkg.dates import format_date\n\ndef run():\n    return format_date(1)\n"
    )
    return store


def _refs_by_symbol(store) -> dict[tuple[str, str], int]:
    conn = db.connect(store.paths.index_db)
    try:
        return {(s["module"], s["name"]): s["refs"] for s in db.all_symbols(conn)}
    finally:
        conn.close()


def test_partial_map_preserves_other_modules(tmp_path):
    store = _project(tmp_path)
    ops.map_repo(store, TorsorConfig())
    ops.map_repo(store, TorsorConfig(), paths=["app.py"])  # rescan app only
    conn = db.connect(store.paths.index_db)
    try:
        mods = db.modules(conn)
    finally:
        conn.close()
    assert "app.py" in mods
    assert "pkg/dates.py" in mods  # wiped before the fix


def test_partial_map_matches_full_map(tmp_path):
    # Rescanning the *referenced* module (pkg/dates.py) alone must still leave
    # format_date.refs == 1 — the ref lives in app.py's preserved edges, so the
    # merged graph must be recomputed to match a pristine full remap.
    store = _project(tmp_path)
    ops.map_repo(store, TorsorConfig())
    full = _refs_by_symbol(store)
    assert full[("pkg/dates.py", "format_date")] == 1

    ops.map_repo(store, TorsorConfig(), paths=["pkg/dates.py"])
    assert _refs_by_symbol(store) == full
