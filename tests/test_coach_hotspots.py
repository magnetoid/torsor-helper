from datetime import datetime

from torsor_helper import db
from torsor_helper.coach import hotspots, report
from torsor_helper.config import TorsorConfig
from torsor_helper.embeddings import HashingEmbedder
from torsor_helper.indexer import reindex
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 1, 9, 30, 0)


def test_find_hotspots_ranks_churned_complex_file(git_project):
    recs = hotspots.find_hotspots(git_project)
    assert recs
    assert recs[0].kind == "hotspot"
    assert recs[0].source == "hot.py"  # most churn × most complexity
    assert recs[0].score > 0


def test_no_hotspots_without_git(tmp_project):
    assert hotspots.find_hotspots(tmp_project) == []


def test_assemble_includes_hotspot_in_git_repo(git_project):
    store = Store(TorsorPaths(git_project), clock=CLOCK)
    conn = db.connect(store.paths.index_db)
    reindex(store, conn, HashingEmbedder(dim=64))
    try:
        recs = report.assemble(store, TorsorConfig(), conn=conn, embedder=HashingEmbedder(dim=64))
    finally:
        conn.close()
    assert any(r.kind == "hotspot" and r.source == "hot.py" for r in recs)


def test_assemble_no_hotspot_offline_non_git(tmp_project):
    store = Store(TorsorPaths(tmp_project), clock=CLOCK)
    conn = db.connect(store.paths.index_db)
    reindex(store, conn, HashingEmbedder(dim=64))
    try:
        recs = report.assemble(store, TorsorConfig(), conn=conn, embedder=HashingEmbedder(dim=64))
    finally:
        conn.close()
    assert not any(r.kind == "hotspot" for r in recs)
