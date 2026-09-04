import pytest

from torsor_helper import cartographer
from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

pytest.importorskip("tree_sitter")


def _ts_repo(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "dates.ts").write_text("export function formatDate(d: Date) { return d.toISOString(); }\n")
    (tmp_path / "src" / "app.ts").write_text(
        "import { formatDate } from './dates';\nexport function run() { return formatDate(new Date()); }\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.ts").write_text("export function nope() {}\n")
    return store


def test_map_impact_and_find_work_on_typescript(tmp_path):
    store = _ts_repo(tmp_path)
    stats = ops.map_repo(store, TorsorConfig())
    assert stats["modules"] == 2 and stats["symbols"] == 2
    impact = ops.impact(store, TorsorConfig(), "formatDate")
    assert [c["caller"] for c in impact["callers"]] == ["run"]
    hits = ops.find_targets(store, TorsorConfig(), "formatDate", mode="fuzzy", limit=5,
                            include_files=False, include_symbols=True)
    assert hits and hits[0]["name"] == "formatDate"


def test_cross_module_refs_and_impact_with_nested_import_path(tmp_path):
    # R10 regression: resolve_relative already returns the canonical key
    # ("lib.utils" for src/lib/utils.ts) — a consumer that re-applies
    # norm_module strips the leading "lib." a second time, producing "utils",
    # which never matches the symbol's own canonical key "lib.utils".
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib").mkdir()
    (tmp_path / "src" / "lib" / "utils.ts").write_text("export function helper() { return 1; }\n")
    (tmp_path / "src" / "app.ts").write_text(
        "import { helper } from './lib/utils';\nexport function f() { return helper(); }\n")

    symbols, _edges = cartographer.scan_repo_with_edges(tmp_path)
    helper_sym = next(s for s in symbols if s.name == "helper")
    assert helper_sym.refs == 1

    ops.map_repo(store, TorsorConfig())
    impact = ops.impact(store, TorsorConfig(), "helper")
    assert [c["caller"] for c in impact["callers"]] == ["f"]
