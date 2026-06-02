from torsor_helper.models import Recommendation


def test_recommendation_defaults():
    r = Recommendation(kind="thin", message="fill the charter", key="thin:charter")
    assert r.severity == "suggest"
    assert r.action == "" and r.source == "" and r.score == 0.0


def test_recommendation_full():
    r = Recommendation(kind="reuse", severity="important", message="reuse format_date",
                       action="Reuse format_date", source="utils/dates.py:12", key="reuse:x", score=3.0)
    assert r.kind == "reuse" and r.severity == "important" and r.score == 3.0
