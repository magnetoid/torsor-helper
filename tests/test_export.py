from datetime import datetime

from torsor_helper import export
from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def _project(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_llms_txt_shape(tmp_path):
    store = _project(tmp_path)
    result = ops.export_project(store, TorsorConfig())
    text = store.paths.llms_txt.read_text(encoding="utf-8")
    assert store.paths.llms_txt.exists()
    assert text.startswith("# ")  # H1 charter title
    assert any(line.startswith(">") for line in text.splitlines())  # summary blockquote
    assert "## Architecture" in text
    assert "(architecture/system-patterns.md)" in text  # markdown link to a real note
    assert result["llms_txt"].endswith("llms.txt")


def test_mermaid_module_diagram_in_overview(tmp_path):
    store = _project(tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "dates.py").write_text("def format_date(d):\n    return d\n")
    (tmp_path / "app.py").write_text("from pkg.dates import format_date\n\ndef run():\n    return format_date(1)\n")
    ops.map_repo(store, TorsorConfig())
    ops.export_project(store, TorsorConfig())
    overview = store.paths.map_overview.read_text(encoding="utf-8")
    assert "```mermaid" in overview
    assert "graph TD" in overview
    assert "-->" in overview  # at least one module dependency edge


def test_export_is_idempotent_no_duplicate_mermaid(tmp_path):
    store = _project(tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "dates.py").write_text("def f(d):\n    return d\n")
    (tmp_path / "app.py").write_text("from pkg.dates import f\n\ndef run():\n    return f(1)\n")
    ops.map_repo(store, TorsorConfig())
    ops.export_project(store, TorsorConfig())
    ops.export_project(store, TorsorConfig())
    overview = store.paths.map_overview.read_text(encoding="utf-8")
    assert overview.count("```mermaid") == 1  # not accumulated across runs


def test_render_module_mermaid_empty_without_edges(tmp_path):
    store = _project(tmp_path)
    from torsor_helper import db
    conn = db.connect(store.paths.index_db)
    try:
        assert export.render_module_mermaid(conn) == ""  # no edges → no diagram
    finally:
        conn.close()
