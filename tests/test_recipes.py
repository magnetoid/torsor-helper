from datetime import datetime

from typer.testing import CliRunner

from torsor_helper import db
from torsor_helper import operations as ops
from torsor_helper.cli import app
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

runner = CliRunner()
CLOCK = lambda: datetime(2026, 6, 10, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_log_op_and_top_ops(tmp_path):
    conn = db.connect(tmp_path / "i.db")
    assert db.SCHEMA_VERSION == 6
    db.log_op(conn, "recall", "auth")
    db.log_op(conn, "recall", "auth")
    db.log_op(conn, "get_intent", "payments")
    top = db.top_ops(conn)
    assert top[0]["op"] == "recall" and top[0]["args"] == "auth" and top[0]["hits"] == 2
    assert any(r["op"] == "get_intent" for r in top)


def test_recall_records_a_recipe(tmp_path):
    store = _store(tmp_path)
    ops.remember(store, "we use RRF for fusion", kind="decision")
    ops.recall(store, TorsorConfig(), "RRF")  # first call creates the index
    ops.recall(store, TorsorConfig(), "RRF")  # subsequent calls are logged
    recs = ops.recipes(store)
    assert any(r["op"] == "recall" and r["args"] == "RRF" for r in recs)


def test_recipes_empty_without_index(tmp_path):
    store = _store(tmp_path)
    assert ops.recipes(store) == []


def test_cli_recipes(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    ops.remember(store, "note", kind="observation")
    ops.recall(store, TorsorConfig(), "something")
    ops.recall(store, TorsorConfig(), "something")
    r = runner.invoke(app, ["recipes", "--root", str(tmp_path)])
    assert r.exit_code == 0
    assert "recall" in r.output
