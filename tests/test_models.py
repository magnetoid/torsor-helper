from pathlib import Path

import pytest
from pydantic import ValidationError

from torsor_helper.models import (
    Frontmatter, MemoryKind, Note, RecallHit, RecallResult, Tier,
)


def test_tier_ordering():
    assert Tier.CHARTER < Tier.ARCHITECTURE < Tier.MAP < Tier.ACTIVE < Tier.EPISODIC


def test_frontmatter_requires_type():
    with pytest.raises(ValidationError):
        Frontmatter(status="active")  # 'type' is required


def test_recall_hit_rejects_negative_score():
    with pytest.raises(ValidationError):
        RecallHit(path="a.md", title="A", tier=Tier.EPISODIC, score=-1.0, snippet="x")


def test_memory_kind_values():
    assert MemoryKind.OBSERVATION.value == "observation"
    assert MemoryKind.HANDOFF.value == "handoff"


def test_frontmatter_defaults_and_extra():
    fm = Frontmatter(type="charter", custom_field="ok")
    assert fm.status == "active"
    assert fm.tags == [] and fm.links == []
    assert fm.model_dump()["custom_field"] == "ok"


def test_note_round_trips_fields():
    note = Note(
        path=Path(".torsor/charter.md"),
        tier=Tier.CHARTER,
        frontmatter=Frontmatter(type="charter"),
        title="Charter",
        body="Body text",
        content_hash="abc",
    )
    assert note.tier is Tier.CHARTER
    assert note.title == "Charter"


def test_recall_result_holds_hits():
    hit = RecallHit(path="a.md", title="A", tier=Tier.EPISODIC, score=1.0, snippet="x")
    res = RecallResult(query="q", hits=[hit], total_tokens=5)
    assert res.hits[0].title == "A"
    assert res.total_tokens == 5
