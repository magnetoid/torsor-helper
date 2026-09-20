"""`torsor export` and `torsor map` must not fight over the same file.

export appended its Mermaid diagram into map/overview.md, which map_repo
re-renders from scratch — so the diagram vanished on the next commit, because
the post-commit hook remaps every time.
"""
from __future__ import annotations

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def _repo(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "core.py").write_text("def engine():\n    return 1\n")
    (tmp_path / "app.py").write_text("from pkg.core import engine\n\ndef run():\n    return engine()\n")
    return store


def test_the_diagram_survives_a_remap(tmp_path):
    store = _repo(tmp_path)
    config = TorsorConfig()
    ops.map_repo(store, config)
    result = ops.export_project(store, config)
    assert result["diagram"], "no diagram was written at all"

    ops.map_repo(store, config, force=True)

    diagram = store.paths.map_dir / "dependencies.md"
    assert diagram.exists(), "the module diagram did not survive `torsor map`"
    assert "graph" in diagram.read_text(encoding="utf-8").lower()


def test_the_overview_is_still_the_map_overview(tmp_path):
    store = _repo(tmp_path)
    config = TorsorConfig()
    ops.map_repo(store, config)
    ops.export_project(store, config)

    overview = (store.paths.map_dir / "overview.md").read_text(encoding="utf-8")

    assert "app.py" in overview
    assert "```mermaid" not in overview, "the diagram belongs in its own note"


def test_exporting_twice_does_not_duplicate_the_diagram(tmp_path):
    store = _repo(tmp_path)
    config = TorsorConfig()
    ops.map_repo(store, config)
    ops.export_project(store, config)
    ops.export_project(store, config)

    text = (store.paths.map_dir / "dependencies.md").read_text(encoding="utf-8")
    assert text.count("```mermaid") == 1
