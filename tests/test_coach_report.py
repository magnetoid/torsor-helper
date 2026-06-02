from datetime import datetime

from torsor_helper.coach import report
from torsor_helper.coach.state import CoachState
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 2, 9, 0, 0)


def _store(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    return store


def test_assemble_returns_hygiene_recs_without_index(tmp_path):
    store = _store(tmp_path)
    recs = report.assemble(store, TorsorConfig(), conn=None, embedder=None)
    kinds = {r.kind for r in recs}
    assert "thin" in kinds
    assert recs[0].severity == "important"


def test_assemble_respects_dismissals(tmp_path):
    store = _store(tmp_path)
    state = CoachState(store.paths.index_dir / "coach_state.json")
    state.dismiss("thin:charter")
    state.save()
    recs = report.assemble(store, TorsorConfig(), conn=None, embedder=None)
    assert all(r.key != "thin:charter" for r in recs)


def test_assemble_limits_and_records_seen(tmp_path):
    store = _store(tmp_path)
    recs = report.assemble(store, TorsorConfig(), conn=None, embedder=None, limit=1)
    assert len(recs) == 1
    state = CoachState(store.paths.index_dir / "coach_state.json")
    assert state.times_shown(recs[0].key) >= 1
