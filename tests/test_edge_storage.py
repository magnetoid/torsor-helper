"""Which reference edges the index keeps.

On a real 3 200-file project the index was 216 MB, and 172 MB of it was
symbol_edges plus its two indexes: 1 071 508 rows, 79% of them unresolved —
references to `self`, `str`, `result`, `monkeypatch`, `len`. Python and JS
resolve an edge while extracting it and have no cross-file resolver, so an edge
unresolved then can never be resolved later; and every query that reads edges
(`who_references`, `call_edges`, `fan_in`, `module_edges`) filters on
`resolved_module IS NOT NULL`. They were written, indexed, and reloaded on every
partial-map merge, and never read.

Go is different: its resolver re-resolves every Go edge across the merged graph
(a bare call can resolve once a sibling file gains the symbol), so Go keeps all
of its edges. The rule is taken from the language registry, not from a list of
names, so a language that gains a cross-file resolver keeps its edges too.
"""
from __future__ import annotations

from torsor_helper import cartographer, db, languages
from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.models import SymbolEdge
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def _project(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "dates.py").write_text("def format_date(d):\n    return str(d)\n")
    (tmp_path / "app.py").write_text(
        "from pkg.dates import format_date\n\n"
        "def run(result):\n    print(len(result))\n    return format_date(result)\n"
    )
    return store


def _stored(store):
    conn = db.connect(store.paths.index_db)
    try:
        return db.load_edges(conn)
    finally:
        conn.close()


def test_unresolvable_python_edges_are_not_stored(tmp_path):
    store = _project(tmp_path)
    ops.map_repo(store, TorsorConfig())
    edges = _stored(store)
    assert edges, "the resolved edge must still be there"
    assert all(e.resolved_module for e in edges), [e.referenced_name for e in edges if not e.resolved_module]
    assert ("run", "format_date") in {(e.caller, e.referenced_name) for e in edges}


def test_impact_and_refs_are_unchanged(tmp_path):
    store = _project(tmp_path)
    ops.map_repo(store, TorsorConfig())
    result = ops.impact(store, TorsorConfig(), "format_date")
    assert result["count"] == 1
    conn = db.connect(store.paths.index_db)
    try:
        refs = {(s["module"], s["name"]): s["refs"] for s in db.all_symbols(conn)}
    finally:
        conn.close()
    assert refs[("pkg/dates.py", "format_date")] == 1


def test_a_partial_map_still_matches_a_full_one(tmp_path):
    """ADR 0008's invariant, with the dropped edges in play: the partial merge
    reloads only what was stored, so it must reach exactly the state a pristine
    full remap reaches."""
    store = _project(tmp_path)
    ops.map_repo(store, TorsorConfig())
    full = sorted((e.caller, e.referenced_name, e.module, e.resolved_module) for e in _stored(store))
    ops.map_repo(store, TorsorConfig(), paths=["app.py"])
    ops.map_repo(store, TorsorConfig(), paths=["pkg/dates.py"])
    assert sorted((e.caller, e.referenced_name, e.module, e.resolved_module) for e in _stored(store)) == full


def test_go_keeps_unresolved_edges_for_its_resolver():
    edges = [
        SymbolEdge(caller="f", referenced_name="Helper", role="call", module="svc/a.go"),
        SymbolEdge(caller="run", referenced_name="self", role="read", module="app.py"),
        SymbolEdge(caller="run", referenced_name="f", role="call", module="app.py", resolved_module="app"),
    ]
    kept = cartographer.persistable_edges(edges)
    names = {(e.module, e.referenced_name) for e in kept}
    if languages.is_available("go"):
        assert ("svc/a.go", "Helper") in names
    assert ("app.py", "self") not in names
    assert ("app.py", "f") in names


def test_the_reported_edge_count_is_what_was_stored(tmp_path):
    """`map` said "1 071 508 reference edge(s)" — every name the extractor saw,
    including the ones thrown away as unresolvable — while `stats` read the
    table. One number, and it is the stored one."""
    store = _project(tmp_path)
    result = ops.map_repo(store, TorsorConfig())
    assert result["edges"] == len(_stored(store))
    skipped = ops.map_repo(store, TorsorConfig())
    assert skipped["skipped"] and skipped["edges"] == result["edges"]


def test_an_index_from_the_old_format_is_remapped_once(tmp_path, monkeypatch):
    """Otherwise an existing index keeps its bloat until some source file
    changes, because an unchanged fingerprint skips the map entirely."""
    store = _project(tmp_path)
    ops.map_repo(store, TorsorConfig())
    conn = db.connect(store.paths.index_db)
    try:
        stamp = db.meta_get(conn, "map_fingerprint")
        db.meta_set(conn, "map_fingerprint", stamp.split(":", 1)[-1])  # as an older version wrote it
        conn.commit()
    finally:
        conn.close()
    assert ops.map_repo(store, TorsorConfig())["skipped"] is False
    assert ops.map_repo(store, TorsorConfig())["skipped"] is True


def test_the_format_migration_gives_the_space_back(tmp_path, monkeypatch):
    """Dropping 79% of the rows does not shrink the file: SQLite keeps freed
    pages until a VACUUM. On the real project the index stayed at 217 MB after
    the remap and fell to 80 MB only once vacuumed, so the one-time migration
    vacuums — and an ordinary remap, which frees nothing, does not."""
    store = _project(tmp_path)
    ops.map_repo(store, TorsorConfig())
    calls = []
    monkeypatch.setattr(db, "vacuum", lambda conn: calls.append(1))

    ops.map_repo(store, TorsorConfig(), force=True)
    assert calls == [], "an ordinary remap must not rewrite the whole file"

    conn = db.connect(store.paths.index_db)
    try:
        stamp = db.meta_get(conn, "map_fingerprint")
        db.meta_set(conn, "map_fingerprint", stamp.split(":", 1)[-1])
        conn.commit()
    finally:
        conn.close()
    ops.map_repo(store, TorsorConfig())
    assert calls == [1]


def test_a_partial_map_that_migrates_first_still_vacuums(tmp_path, monkeypatch):
    """The post-commit hook's partial map clears the fingerprint, so if it is
    the first thing to touch an old index, the old stamp is gone by the time a
    full map runs."""
    store = _project(tmp_path)
    ops.map_repo(store, TorsorConfig())
    conn = db.connect(store.paths.index_db)
    try:
        stamp = db.meta_get(conn, "map_fingerprint")
        db.meta_set(conn, "map_fingerprint", stamp.split(":", 1)[-1])
        conn.commit()
    finally:
        conn.close()
    calls = []
    monkeypatch.setattr(db, "vacuum", lambda conn: calls.append(1))
    ops.map_repo(store, TorsorConfig(), paths=["app.py"])
    assert calls == [1]
