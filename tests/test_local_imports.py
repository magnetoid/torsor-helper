"""A function-local import is still an import.

`_import_aliases` read only `tree.body`, so a name bound inside a function
resolved to nothing: the callee's ref count was short, and `impact` never
listed the caller. Deferred imports are ordinary Python — used for optional
dependencies, for startup cost, and (in this very codebase, until recently) to
dodge cycles — so the omission was systematic, not an edge case.

guard and deps already walk the whole tree for imports. This makes the three
agree.
"""
from __future__ import annotations

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.languages.python import extract_edges
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def _repo(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "core.py").write_text("def engine():\n    return 1\n")
    return store


def test_a_name_imported_inside_a_function_resolves():
    edges = extract_edges(
        "def run():\n    from pkg.core import engine\n    return engine()\n", "local.py"
    )
    engine = next(e for e in edges if e.referenced_name == "engine")
    assert engine.resolved_module == "pkg.core"


def test_a_locally_imported_module_resolves_exactly_as_a_top_level_one_does():
    """Parity is the contract, not perfection.

    `from pkg import core` binds `core` to the module imported FROM, so
    `core.engine()` resolves to "pkg" — the extractor cannot tell whether
    `core` is a submodule or a name without touching the filesystem, and ADR
    0004 says it resolves only the reliable cases. That limit is pre-existing
    and identical at the top level; what matters here is that a deferred import
    is no longer treated as absent."""
    top = extract_edges("from pkg import core\n\ndef run():\n    return core.engine()\n", "m.py")
    local = extract_edges("def run():\n    from pkg import core\n    return core.engine()\n", "m.py")

    def resolved(edges):
        return next(e.resolved_module for e in edges if e.referenced_name == "engine")

    assert resolved(local) == resolved(top) == "pkg"


def test_impact_lists_a_caller_that_imports_locally(tmp_path):
    store = _repo(tmp_path)
    (tmp_path / "top.py").write_text("from pkg.core import engine\n\ndef run():\n    return engine()\n")
    (tmp_path / "local.py").write_text("def run():\n    from pkg.core import engine\n    return engine()\n")
    ops.map_repo(store, TorsorConfig())

    modules = {c["module"] for c in ops.impact(store, TorsorConfig(), "engine")["callers"]}

    assert modules == {"top.py", "local.py"}


def test_a_top_level_import_still_wins_for_the_same_name():
    # A local import that shadows a top-level one is resolved to the local
    # binding, which is what the code actually calls.
    edges = extract_edges(
        "from pkg.other import engine\n\n"
        "def run():\n    from pkg.core import engine\n    return engine()\n",
        "local.py",
    )
    engine = next(e for e in edges if e.referenced_name == "engine" and e.caller == "run")
    assert engine.resolved_module == "pkg.core"
