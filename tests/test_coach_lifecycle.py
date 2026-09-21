"""Recommendation lifecycle and contradiction detection.

Two gaps from the Coach spec §7: nothing ever noticed that a recommendation had
been *fixed*, so a problem you solved left no trace and an old one just sank
below the limit; and nothing checked whether two active decisions disagree with
each other, which is the failure mode a growing ADR set has and a linter cannot
see.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from torsor_helper.coach import contradiction, report
from torsor_helper.coach.state import CoachState
from torsor_helper.config import TorsorConfig
from torsor_helper.models import Frontmatter, Recommendation
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


# ---- contradiction ----

def test_two_decisions_that_disagree_are_flagged(tmp_path):
    store = _store(tmp_path)
    _decision(store, 1, "Use dependency injection for services", "Wire services through a container.")
    _decision(store, 2, "Never use dependency injection for services", "Construct services directly.")
    recs = contradiction.find_contradictions(store)
    assert [r.kind for r in recs] == ["contradiction"]
    assert "0001" in recs[0].message and "0002" in recs[0].message


def test_two_decisions_about_different_things_are_not_flagged(tmp_path):
    store = _store(tmp_path)
    _decision(store, 1, "Use Postgres for the primary store", "It is the primary store.")
    _decision(store, 2, "Never use Redis as the system of record", "Cache only.")
    assert contradiction.find_contradictions(store) == []


def test_two_decisions_that_agree_are_not_flagged(tmp_path):
    store = _store(tmp_path)
    _decision(store, 1, "Use dependency injection for services", "Wire through a container.")
    _decision(store, 2, "Use dependency injection for handlers", "Wire through a container.")
    assert contradiction.find_contradictions(store) == []


def test_a_superseded_decision_is_not_a_contradiction(tmp_path):
    """Supersession is how a decision is *meant* to be reversed."""
    store = _store(tmp_path)
    old = store.paths.decisions_dir / "0001-x.md"
    store.write_note(old, Frontmatter(type="decision", status="superseded"),
                     "Use dependency injection for services", "Wire through a container.")
    _decision(store, 2, "Never use dependency injection for services", "Construct directly.")
    assert contradiction.find_contradictions(store) == []


def test_an_explicit_supersedes_link_is_not_a_contradiction(tmp_path):
    store = _store(tmp_path)
    _decision(store, 1, "Use dependency injection for services", "Wire through a container.")
    store.write_note(
        store.paths.decisions_dir / "0002-x.md",
        Frontmatter(type="decision", supersedes=["0001-x"]),
        "Never use dependency injection for services", "Construct directly.",
    )
    assert contradiction.find_contradictions(store) == []


def test_non_decisions_are_never_compared(tmp_path):
    store = _store(tmp_path)
    store.write_note(store.paths.decisions_dir / "0001-x.md", Frontmatter(type="note"),
                     "Use dependency injection for services", "Wire through a container.")
    store.write_note(store.paths.decisions_dir / "0002-x.md", Frontmatter(type="note"),
                     "Never use dependency injection for services", "Construct directly.")
    assert contradiction.find_contradictions(store) == []


def test_this_repos_own_adrs_contain_no_contradiction():
    """The precision test that matters. torsor's own 16 ADRs do not contradict
    each other, so a check that fires on them is wrong, not sensitive."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    store = Store(TorsorPaths(root))
    assert contradiction.find_contradictions(store) == []


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Use dependency injection", 1),
        ("Always prefer composition", 1),
        ("Never use global state", -1),
        ("Avoid global state", -1),
        ("Do not use global state", -1),
        ("Adapters depend on core, never the reverse", -1),
        ("Cleanup is plan-then-apply", 0),
    ],
)
def test_polarity(title, expected):
    assert contradiction.polarity(title) == expected


def test_contradiction_is_wired_into_the_coach(tmp_path):
    store = _store(tmp_path)
    _decision(store, 1, "Use dependency injection for services", "Wire through a container.")
    _decision(store, 2, "Never use dependency injection for services", "Construct directly.")
    kinds = {r.kind for r in report.assemble(store, TorsorConfig(), limit=20)}
    assert "contradiction" in kinds


def test_a_contradiction_can_be_dismissed(tmp_path):
    store = _store(tmp_path)
    _decision(store, 1, "Use dependency injection for services", "Wire through a container.")
    _decision(store, 2, "Never use dependency injection for services", "Construct directly.")
    rec = contradiction.find_contradictions(store)[0]

    state = CoachState(report._coach_state_path(store), clock=CLOCK)
    state.dismiss(rec.key)
    state.save()
    kinds = {r.kind for r in report.assemble(store, TorsorConfig(), limit=20)}
    assert "contradiction" not in kinds


def test_the_contradiction_key_is_order_independent(tmp_path):
    """Or dismissing it once would not stick the next time the pair is compared
    in the other order."""
    store = _store(tmp_path)
    _decision(store, 1, "Use dependency injection for services", "Wire through a container.")
    _decision(store, 2, "Never use dependency injection for services", "Construct directly.")
    key = contradiction.find_contradictions(store)[0].key
    assert key == contradiction._pair_key("0002-x.md", "0001-x.md")


def test_contradiction_is_advisory(tmp_path):
    store = _store(tmp_path)
    _decision(store, 1, "Use dependency injection for services", "Wire through a container.")
    _decision(store, 2, "Never use dependency injection for services", "Construct directly.")
    assert all(isinstance(r, Recommendation) and r.severity != "important"
               for r in contradiction.find_contradictions(store))


def test_the_fixed_line_survives_a_crowded_page(tmp_path):
    """It ranks into the info band, so on a busy project it would sort off the
    end of the page — while the state that produced it has already been dropped,
    so the good news would be reported into a void and never come back."""
    store = _store(tmp_path)
    state = CoachState(report._coach_state_path(store), clock=CLOCK)
    state.seen("hotspot:gone.py")
    state.save()

    recs = report.assemble(store, TorsorConfig(), limit=1)
    assert recs[0].kind == "resolved"
    assert len(recs) == 2, "the fixed line is extra, not one of the limit slots"
