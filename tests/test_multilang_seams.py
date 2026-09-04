"""Seam tests: the multi-language map through the consumers that sit on top of
it — compute_refs across three languages at once, `connect`, `export`, and the
partial-remap merge (which round-trips edges through SQLite)."""
import pytest

from torsor_helper import cartographer, db, export
from torsor_helper import languages
from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

needs_ts = pytest.mark.skipif(not languages.is_available("typescript"), reason="needs [languages] extra")
needs_go = pytest.mark.skipif(not languages.is_available("go"), reason="needs [languages] extra")
needs_all = pytest.mark.skipif(
    not (languages.is_available("typescript") and languages.is_available("go")),
    reason="needs [languages] extra",
)


def _ts_repo(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils.ts").write_text("export function helper() { return 1; }\n")
    (tmp_path / "src" / "app.ts").write_text(
        "import { helper } from './utils';\nexport function run() { return helper(); }\n"
    )
    return store


@needs_all
def test_mixed_python_typescript_and_go_repo_refs_and_methods(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "dates.py").write_text("def format_date(d):\n    return d\n")
    (tmp_path / "app.py").write_text(
        "from pkg.dates import format_date\n\ndef run():\n    return format_date(1)\n"
    )
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "utils.ts").write_text(
        "export function helper() { return 1; }\nexport class Box { get() { return 2; } }\n"
    )
    (tmp_path / "web" / "app.ts").write_text(
        "import { helper } from './utils';\nexport function run() { return helper(); }\n"
    )
    (tmp_path / "svc").mkdir()
    (tmp_path / "svc" / "store.go").write_text(
        "package svc\n\ntype Store struct{}\n\nfunc New() *Store { return nil }\n\n"
        "func (s *Store) Get() int { return 1 }\n"
    )
    (tmp_path / "svc" / "use.go").write_text("package svc\n\nfunc Build() *Store { return New() }\n")

    symbols, _edges = cartographer.scan_repo_with_edges(tmp_path)
    refs = {(s.module, s.name): s.refs for s in symbols}
    assert refs[("pkg/dates.py", "format_date")] == 1
    assert refs[("web/utils.ts", "helper")] == 1
    assert refs[("svc/store.go", "New")] == 1
    # Methods score 0 by design (ADR 0004) — in every language.
    methods = [s for s in symbols if "." in s.name]
    assert {"Box.get", "Store.Get"} <= {s.name for s in methods}
    assert all(s.refs == 0 for s in methods)


@needs_ts
def test_connect_walks_a_typescript_call_graph_end_to_end(tmp_path):
    store = _ts_repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    res = ops.connect(store, TorsorConfig(), "run", "helper")
    assert res["found"] is True
    assert [hop["symbol"] for hop in res["path"]] == ["run", "helper"]
    # Canonical dotted keys, not file relpaths ("src/" stripped, ".ts" stripped).
    assert [hop["module"] for hop in res["path"]] == ["app", "utils"]


@needs_ts
def test_export_mermaid_draws_a_typescript_module_edge(tmp_path):
    store = _ts_repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    conn = db.connect(store.paths.index_db)
    try:
        mermaid = export.render_module_mermaid(conn)
    finally:
        conn.close()
    assert "n_app --> n_utils" in mermaid


@needs_go
def test_go_import_hint_survives_a_partial_remap(tmp_path):
    # Critical: `hint` distinguishes `errors.New` (qualified, unresolvable) from
    # a bare same-package `New()`. It used to be dropped by the DB, so after a
    # partial remap re-loaded the edges the stdlib call resolved to the local
    # `New` and inflated its ref count.
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "svc").mkdir()
    (tmp_path / "svc" / "a.go").write_text(
        "package svc\n\nimport \"errors\"\n\ntype Store struct{}\n\n"
        "func New() (*Store, error) { return nil, errors.New(\"boom\") }\n"
    )
    (tmp_path / "svc" / "other.go").write_text(
        "package svc\n\nfunc Build() (*Store, error) { return New() }\n"
    )

    ops.map_repo(store, TorsorConfig())
    ops.map_repo(store, TorsorConfig(), paths=["svc/other.go"])

    conn = db.connect(store.paths.index_db)
    try:
        edges = db.load_edges(conn)
        symbols = db.load_symbols(conn)
    finally:
        conn.close()

    qualified = [e for e in edges if e.referenced_name == "New" and e.hint == "errors"]
    assert len(qualified) == 1
    assert qualified[0].resolved_module is None
    new_sym = next(s for s in symbols if s.name == "New")
    assert new_sym.refs == 1  # only Build() calls it — errors.New must not count
