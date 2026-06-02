from torsor_helper.coach.state import CoachState


def test_dismiss_and_persist(tmp_path):
    p = tmp_path / "coach_state.json"
    state = CoachState(p)
    assert state.is_dismissed("thin:charter") is False
    state.dismiss("thin:charter")
    state.save()
    reloaded = CoachState(p)
    assert reloaded.is_dismissed("thin:charter") is True


def test_seen_counts(tmp_path):
    state = CoachState(tmp_path / "coach_state.json")
    state.seen("uncharted")
    state.seen("uncharted")
    assert state.times_shown("uncharted") == 2
    assert state.times_shown("never") == 0


def test_corrupt_state_resets(tmp_path):
    p = tmp_path / "coach_state.json"
    p.write_text("{not valid json")
    state = CoachState(p)  # must not raise
    assert state.is_dismissed("x") is False
