"""Rough edges found by running torsor on a real 3 200-file project.

Each one is small and each one is the kind a self-hosted test suite does not
produce: nobody writes an invalid escape sequence or a NUL byte into their own
fixtures.
"""
from __future__ import annotations

import warnings

import pytest

from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path))
    store.scaffold()
    return store


def test_mapping_a_project_with_invalid_escapes_is_silent(tmp_path):
    """`map` printed `<unknown>:625: SyntaxWarning: invalid escape sequence '\\d'`
    twice on the real project — no filename, nothing the user could act on, and
    about their code rather than torsor's.

    Recorded, not turned into errors: the first version of this test used
    simplefilter("error"), which makes ast.parse raise SyntaxError — swallowed by
    the extractor, the file silently skipped, and the test green for the wrong
    reason. So it also asserts the function in that file was actually mapped."""
    from torsor_helper import db

    store = _store(tmp_path)
    (tmp_path / "a.py").write_text('import re\nP = re.compile("\\d+")\ndef f():\n    return P\n',
                                   encoding="utf-8")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ops.map_repo(store, TorsorConfig())
        ops.recommend(store, TorsorConfig())
    assert not [w for w in caught if issubclass(w.category, SyntaxWarning)]
    conn = db.connect(store.paths.index_db)
    try:
        assert "f" in {s.name for s in db.load_symbols(conn)}, "the file must be mapped, not skipped"
    finally:
        conn.close()


def test_a_nul_byte_does_not_take_the_map_down(tmp_path):
    """A regression guard, not a fix. `compile()`'s documented contract raises
    ValueError for NUL bytes and every parse site caught only SyntaxError; the
    interpreters tested here (3.11, 3.12, 3.13) all raise SyntaxError instead,
    so this passed before too. parse_quietly catches both, per the contract."""
    store = _store(tmp_path)
    (tmp_path / "bad.py").write_bytes(b"x = 1\x00\n")
    (tmp_path / "good.py").write_text("def g():\n    return 1\n", encoding="utf-8")
    result = ops.map_repo(store, TorsorConfig())
    assert result["symbols"] >= 1


@pytest.mark.parametrize("source", ["x = 1\x00\n", "def (:\n", 'P = "\\d"\n'])
def test_parse_quietly(source):
    from torsor_helper.languages.python import parse_quietly

    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        tree = parse_quietly(source)
    assert tree is None or tree.body is not None


def test_coach_accepts_a_limit_on_the_cli(tmp_path):
    """The MCP `recommend` tool takes `limit`; the CLI could never show more than
    eight. Found by reaching for it on the real project."""
    from typer.testing import CliRunner

    from torsor_helper.cli import app

    _store(tmp_path)
    one = CliRunner().invoke(app, ["coach", "--root", str(tmp_path), "--limit", "1"])
    assert one.exit_code == 0, one.output
    assert len([ln for ln in one.output.splitlines() if ln.startswith("[")]) == 1
