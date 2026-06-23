from datetime import datetime

from torsor_helper import db
from torsor_helper import operations as ops
from torsor_helper.coach import hubs
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 23, 9, 0, 0)


def _god_node_repo(tmp_path):
    """One symbol (`helper`) called from many modules -> a hub / God node.
    Several leaf functions with no callers -> not hubs."""
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    (tmp_path / "util.py").write_text("def helper():\n    return 1\n")
    for i in range(6):
        (tmp_path / f"mod{i}.py").write_text(
            f"from util import helper\n\ndef use{i}():\n    return helper()\n"
        )
    return store


def test_find_hubs_flags_high_fan_in_symbol(tmp_path):
    store = _god_node_repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    conn = db.connect(store.paths.index_db)
    try:
        found = hubs.find_hubs(conn, min_fan_in=5)
    finally:
        conn.close()
    names = {name for _mod, name, _fanin in found}
    assert "helper" in names
    fanin = {name: fi for _mod, name, fi in found}["helper"]
    assert fanin >= 6


def test_find_hubs_quiet_when_nothing_is_a_hub(tmp_path):
    store = _god_node_repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    conn = db.connect(store.paths.index_db)
    try:
        found = hubs.find_hubs(conn, min_fan_in=100)
    finally:
        conn.close()
    assert found == []


def test_find_hub_recs_returns_recommendation(tmp_path):
    store = _god_node_repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    conn = db.connect(store.paths.index_db)
    try:
        recs = hubs.find_hub_recs(conn, min_fan_in=5)
    finally:
        conn.close()
    assert recs
    rec = recs[0]
    assert rec.kind == "hub"
    assert "helper" in rec.message
    assert rec.key == "hub:util:helper"


def test_find_hub_recs_empty_without_conn(tmp_path):
    assert hubs.find_hub_recs(None) == []
