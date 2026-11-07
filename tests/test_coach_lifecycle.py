"""Recommendation lifecycle.

A gap from the Coach spec §7: nothing ever noticed that a recommendation had
been *fixed*, so a problem you solved left no trace and an old one just sank
below the limit.
"""
from __future__ import annotations

from datetime import datetime


from torsor_helper.coach import report
from torsor_helper.coach.state import CoachState
from torsor_helper.config import TorsorConfig
from torsor_helper.models import Frontmatter
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)
LATER = lambda: datetime(2026, 6, 15, 9, 30, 0)


def _store(tmp_path, clock=CLOCK):
    store = Store(TorsorPaths(tmp_path), clock=clock)
    store.scaffold()
    return store


def _decision(store, number, title, body):
    return store.write_note(
        store.paths.decisions_dir / f"{number:04d}-x.md",
        Frontmatter(type="decision"), title, body,
    )


# ---- CoachState: first_seen / last_shown ----

def test_state_records_when_a_recommendation_was_first_seen(tmp_path):
    state = CoachState(tmp_path / "s.json", clock=CLOCK)
    state.seen("hotspot:a")
    assert state.first_seen("hotspot:a") == "2026-06-01"

    later = CoachState(tmp_path / "s.json", clock=LATER)
    state.save()
    later = CoachState(tmp_path / "s.json", clock=LATER)
    later.seen("hotspot:a")
    assert later.first_seen("hotspot:a") == "2026-06-01", "first_seen must not move"
    assert later.last_shown("hotspot:a") == "2026-06-15"


def test_days_open_counts_from_first_seen(tmp_path):
    state = CoachState(tmp_path / "s.json", clock=CLOCK)
    state.seen("hotspot:a")
    state.save()
    assert CoachState(tmp_path / "s.json", clock=LATER).days_open("hotspot:a") == 14


def test_days_open_is_zero_for_an_unseen_key(tmp_path):
    assert CoachState(tmp_path / "s.json", clock=CLOCK).days_open("never-seen") == 0


def test_a_corrupt_state_file_still_resets_cleanly(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{not json", encoding="utf-8")
    state = CoachState(path, clock=CLOCK)
    state.seen("a")
    assert state.times_shown("a") == 1


# ---- resolution ----

def test_resolve_missing_returns_keys_that_stopped_appearing(tmp_path):
    state = CoachState(tmp_path / "s.json", clock=CLOCK)
    state.seen("hotspot:a")
    state.seen("hotspot:b")
    assert state.resolve_missing({"hotspot:a"}) == ["hotspot:b"]


def test_a_resolved_key_is_forgotten_so_it_reports_once(tmp_path):
    state = CoachState(tmp_path / "s.json", clock=CLOCK)
    state.seen("hotspot:b")
    assert state.resolve_missing(set()) == ["hotspot:b"]
    assert state.resolve_missing(set()) == []


def test_a_key_never_shown_is_not_resolved(tmp_path):
    """Something that never surfaced was never fixed — claiming otherwise is a lie."""
    state = CoachState(tmp_path / "s.json", clock=CLOCK)
    state.dismiss("hotspot:c")
    assert state.resolve_missing(set()) == []


def test_a_dismissed_key_is_not_resolved(tmp_path):
    state = CoachState(tmp_path / "s.json", clock=CLOCK)
    state.seen("hotspot:d")
    state.dismiss("hotspot:d")
    assert state.resolve_missing(set()) == []
    assert state.is_dismissed("hotspot:d"), "a dismissal must survive resolution sweeps"


# ---- assemble: the "fixed since last time" line ----

def test_assemble_reports_what_was_fixed(tmp_path):
    store = _store(tmp_path)
    state = CoachState(report._coach_state_path(store), clock=CLOCK)
    state.seen("hotspot:gone.py")
    state.save()

    recs = report.assemble(store, TorsorConfig())
    resolved = [r for r in recs if r.kind == "resolved"]
    assert len(resolved) == 1
    assert "hotspot:gone.py" in resolved[0].message


def test_the_resolved_line_appears_once(tmp_path):
    store = _store(tmp_path)
    state = CoachState(report._coach_state_path(store), clock=CLOCK)
    state.seen("hotspot:gone.py")
    state.save()

    report.assemble(store, TorsorConfig())
    again = report.assemble(store, TorsorConfig())
    assert [r for r in again if r.kind == "resolved"] == []


def test_a_resolved_line_never_resolves_itself(tmp_path):
    """The regress: the `resolved` rec is itself shown, then absent next run, so
    a naive sweep would report that the report was fixed, forever."""
    store = _store(tmp_path)
    state = CoachState(report._coach_state_path(store), clock=CLOCK)
    state.seen("hotspot:gone.py")
    state.save()

    report.assemble(store, TorsorConfig())
    report.assemble(store, TorsorConfig())
    third = report.assemble(store, TorsorConfig())
    assert [r.kind for r in third if r.kind == "resolved"] == []


def test_recommendations_still_present_are_not_reported_as_fixed(tmp_path):
    store = _store(tmp_path)
    first = report.assemble(store, TorsorConfig())
    assert first, "the seed project should produce at least one recommendation"
    second = report.assemble(store, TorsorConfig())
    assert [r for r in second if r.kind == "resolved"] == []


def test_a_recommendation_below_the_limit_is_not_reported_as_fixed(tmp_path):
    """Resolution compares against everything computed, not the truncated page —
    otherwise raising `limit` would "fix" things and lowering it would un-fix them."""
    store = _store(tmp_path)
    report.assemble(store, TorsorConfig(), limit=8)
    narrow = report.assemble(store, TorsorConfig(), limit=1)
    assert [r for r in narrow if r.kind == "resolved"] == []


def test_session_digest_never_claims_something_was_fixed(tmp_path):
    """It runs three index-free checks; a key it does not compute is absent
    because it was not looked for, not because it was solved."""
    store = _store(tmp_path)
    state = CoachState(report._coach_state_path(store), clock=CLOCK)
    state.seen("hotspot:gone.py")
    state.save()
    assert [r for r in report.session_digest(store) if r.kind == "resolved"] == []
    assert CoachState(report._coach_state_path(store), clock=CLOCK).times_shown("hotspot:gone.py") == 1


# ---- gentle escalation ----

def test_an_old_important_recommendation_says_how_long_it_has_been_open(tmp_path):
    store = _store(tmp_path, clock=LATER)
    state = CoachState(report._coach_state_path(store), clock=CLOCK)
    for _ in range(3):
        state.seen("thin:charter")
    state.save()

    recs = report.assemble(store, TorsorConfig())
    charter = next(r for r in recs if r.key == "thin:charter")
    assert "14 days" in charter.message


def test_a_fresh_recommendation_says_nothing_about_age(tmp_path):
    store = _store(tmp_path)
    charter = next(r for r in report.assemble(store, TorsorConfig()) if r.key == "thin:charter")
    assert "days" not in charter.message


def test_escalation_does_not_reorder_anything(tmp_path, tmp_path_factory):
    """It adds information, not position.

    Compared at equal times_shown and different ages, because times_shown IS the
    decay that keeps the Coach from nagging — varying it would measure that
    instead of this, which is what the first version of this test did."""
    def keys_for(root, first_seen_clock):
        store = _store(root, clock=LATER)
        state = CoachState(report._coach_state_path(store), clock=first_seen_clock)
        for _ in range(3):
            state.seen("thin:charter")
        state.save()
        return [r.key for r in report.assemble(store, TorsorConfig())]

    old = keys_for(tmp_path_factory.mktemp("old"), CLOCK)
    fresh = keys_for(tmp_path_factory.mktemp("fresh"), LATER)
    assert old == fresh
