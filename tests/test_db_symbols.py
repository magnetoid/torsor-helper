from torsor_helper import db
from torsor_helper.models import Symbol, SymbolEdge


def _conn(tmp_path):
    return db.connect(tmp_path / "torsor.db")


def _syms():
    return [
        Symbol(name="format_date", kind="function", signature="format_date(d)", module="dates.py", line=1, doc="Format a date.", refs=3),
        Symbol(name="Cartographer", kind="class", signature="Cartographer", module="cart.py", line=1, refs=1),
    ]


def test_schema_version_and_symbol_tables_exist(tmp_path):
    conn = _conn(tmp_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "symbols" in tables
    assert "symbol_edges" in tables
    assert "complexity_snapshot" in tables
    assert int(db.meta_get(conn, "schema_version")) == db.SCHEMA_VERSION == 4


def test_replace_all_edges_and_who_references(tmp_path):
    conn = _conn(tmp_path)
    db.replace_all_edges(conn, [
        SymbolEdge(caller="run", referenced_name="format_date", role="call", module="app.py", resolved_module="pkg.dates"),
        SymbolEdge(caller="run", referenced_name="obj", role="read", module="app.py", resolved_module=None),
    ])
    db.replace_all_edges(conn, [  # idempotent: replaces, doesn't accumulate
        SymbolEdge(caller="run", referenced_name="format_date", role="call", module="app.py", resolved_module="pkg.dates"),
    ])
    callers = db.who_references(conn, "pkg.dates", "format_date")
    assert ("run", "app.py") in callers


def test_replace_all_symbols_is_idempotent(tmp_path):
    conn = _conn(tmp_path)
    db.replace_all_symbols(conn, _syms())
    db.replace_all_symbols(conn, _syms())
    assert sorted(db.modules(conn)) == ["cart.py", "dates.py"]


def test_search_symbols_by_name_and_signature(tmp_path):
    conn = _conn(tmp_path)
    db.replace_all_symbols(conn, _syms())
    hits = db.search_symbols(conn, "date")
    assert any(s.name == "format_date" for s in hits)
    assert all(isinstance(s, Symbol) for s in hits)
    assert db.search_symbols(conn, "   ") == []
