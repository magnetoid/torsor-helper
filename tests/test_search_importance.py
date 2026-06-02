from datetime import datetime

from torsor_helper import db
from torsor_helper.config import TorsorConfig
from torsor_helper.embeddings import HashingEmbedder
from torsor_helper.indexer import reindex
from torsor_helper.models import Frontmatter, Tier
from torsor_helper.paths import TorsorPaths
from torsor_helper.search import _importance, hybrid_search
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)
FLOORS = {"CHARTER": 1.0, "ARCHITECTURE": 1.0, "MAP": 0.9, "ACTIVE": 0.85, "EPISODIC": 0.7}


def test_importance_floor_for_fresh_note():
    # access_count=0 sits exactly at the floor — never suppressed below it (no cold start)
    assert _importance(Tier.EPISODIC, 0, FLOORS) == 0.7


def test_importance_stable_tiers_never_decay():
    assert _importance(Tier.CHARTER, 0, FLOORS) == 1.0
    assert _importance(Tier.CHARTER, 100, FLOORS) == 1.0
    assert _importance(Tier.ARCHITECTURE, 50, FLOORS) == 1.0


def test_importance_monotonic_toward_one():
    a = _importance(Tier.EPISODIC, 1, FLOORS)
    b = _importance(Tier.EPISODIC, 50, FLOORS)
    assert 0.7 < a < b < 1.0


def test_frequently_recalled_note_floats_up(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()
    # two equally-relevant EPISODIC notes (unique terms so nothing else matches)
    store.write_note(store.paths.insights_dir / "a.md", Frontmatter(type="insight"), "A", "zqxw retrieval marker payload")
    store.write_note(store.paths.insights_dir / "b.md", Frontmatter(type="insight"), "B", "zqxw retrieval marker payload")
    conn = db.connect(tmp_path / "i.db")
    emb = HashingEmbedder(dim=128)
    reindex(store, conn, emb)
    cfg = TorsorConfig()

    a_path = str(store.paths.insights_dir / "a.md")
    b_path = str(store.paths.insights_dir / "b.md")

    base_order = [h.path for h in hybrid_search(conn, emb, cfg, "zqxw retrieval marker", limit=8).hits]
    pair = [p for p in base_order if p in (a_path, b_path)]
    assert len(pair) == 2
    lower = pair[-1]  # the lower-ranked of the two equally-relevant notes

    db.bump_access(conn, [lower] * 50)
    boosted_order = [h.path for h in hybrid_search(conn, emb, cfg, "zqxw retrieval marker", limit=8).hits]
    boosted_pair = [p for p in boosted_order if p in (a_path, b_path)]
    assert boosted_pair[0] == lower  # the frequently-recalled note now leads the pair
