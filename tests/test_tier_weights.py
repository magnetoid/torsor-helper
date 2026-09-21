"""The per-tier recall weights must have exactly one definition. search.py
(indexed path) and recall.py (keyword fallback) previously each kept an
independent copy; a change to one would silently diverge the two rankings.
These tests pin them to the single canonical mapping in models.py."""
from torsor_helper import recall
from torsor_helper.models import TIER_WEIGHTS, Tier


def test_canonical_weights_cover_every_tier():
    assert set(TIER_WEIGHTS) == set(Tier)


def test_search_and_recall_share_the_canonical_object():
    # Identity, not equality: equality would still pass with a duplicated dict.
    # search scores through recall_weight, which reads the one table; a map
    # note for test code is the only adjustment on top of it.
    from torsor_helper.models import recall_weight

    assert all(recall_weight(t, "src/app.py") == TIER_WEIGHTS[t] for t in Tier)
    assert recall._DEFAULT_TIER_WEIGHTS is TIER_WEIGHTS
