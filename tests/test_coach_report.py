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


def test_decay_sinks_frequently_shown_recs(tmp_path):
    # A rec shown many times sinks within its severity band (so the Coach never nags).
    store = _store(tmp_path)
    state = CoachState(store.paths.index_dir / "coach_state.json")
    for _ in range(5):
        state.seen("thin:charter")
    state.save()
    recs = report.assemble(store, TorsorConfig(), conn=None, embedder=None)
    thin_keys = [r.key for r in recs if r.kind == "thin"]
    assert thin_keys, "expected thin recs on a fresh scaffold"
    assert thin_keys[-1] == "thin:charter"  # heavily-shown charter ranks last among thins


def test_session_digest_is_index_free_and_respects_dismissal(tmp_path):
    store = _store(tmp_path)  # fresh scaffold -> thin (important) + stale
    digest = report.session_digest(store, limit=3)
    assert digest and digest[0].severity == "important"  # thin ranks first
    assert all(r.kind in ("thin", "stale", "unruled") for r in digest)  # no uncharted (index-free)
    # dismissed keys are filtered out
    from torsor_helper.coach.state import CoachState
    st = CoachState(store.paths.index_dir / "coach_state.json")
    st.dismiss("thin:charter")
    st.save()
    assert all(r.key != "thin:charter" for r in report.session_digest(store))
