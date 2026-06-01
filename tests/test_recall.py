from pathlib import Path

from torsor_helper.models import Frontmatter, Note, Tier
from torsor_helper.recall import keyword_recall


def _note(title, body, tier, name):
    return Note(
        path=Path(f"{name}.md"),
        tier=tier,
        frontmatter=Frontmatter(type="note"),
        title=title,
        body=body,
        content_hash=name,
    )


def test_recall_ranks_matches_and_skips_misses():
    notes = [
        _note("Auth", "login and auth tokens", Tier.EPISODIC, "a"),
        _note("Payments", "stripe billing", Tier.EPISODIC, "b"),
        _note("Auth design", "auth auth auth layering", Tier.ARCHITECTURE, "c"),
    ]
    res = keyword_recall(notes, "auth", limit=8)
    paths = [h.path for h in res.hits]
    assert "b.md" not in paths  # no match
    assert paths[0] == "c.md"   # higher freq * architecture weight wins
    assert res.total_tokens > 0


def test_recall_empty_query_returns_no_hits():
    notes = [_note("X", "y", Tier.EPISODIC, "x")]
    res = keyword_recall(notes, "   ", limit=8)
    assert res.hits == []


def test_recall_respects_token_budget():
    big = "auth " * 1000
    notes = [_note(f"N{i}", big, Tier.EPISODIC, f"n{i}") for i in range(10)]
    res = keyword_recall(notes, "auth", limit=10, max_tokens=50, chars_per_token=4)
    assert res.total_tokens <= 50 or len(res.hits) == 1


def test_recall_is_deterministic():
    notes = [
        _note("A", "auth", Tier.EPISODIC, "a"),
        _note("B", "auth", Tier.EPISODIC, "b"),
    ]
    first = keyword_recall(notes, "auth")
    second = keyword_recall(notes, "auth")
    assert [h.path for h in first.hits] == [h.path for h in second.hits]
