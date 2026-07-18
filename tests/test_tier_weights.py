"""The per-tier recall weights must have exactly one definition. search.py
(indexed path) and recall.py (keyword fallback) previously each kept an
independent copy; a change to one would silently diverge the two rankings.
These tests pin them to the single canonical mapping in models.py."""
from torsor_helper import recall, search
from torsor_helper.models import TIER_WEIGHTS, Tier


def test_canonical_weights_cover_every_tier():
    assert set(TIER_WEIGHTS) == set(Tier)


def test_search_and_recall_share_the_canonical_object():
    # Identity, not equality: equality would still pass with a duplicated dict.
    assert search._TIER_WEIGHTS is TIER_WEIGHTS
    assert recall._DEFAULT_TIER_WEIGHTS is TIER_WEIGHTS
