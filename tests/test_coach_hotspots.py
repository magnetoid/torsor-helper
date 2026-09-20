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


def test_history_args_bounds_the_git_log_window():
    from torsor_helper.coach.hotspots import history_args

    assert history_args(365) == ["--since", "365 days ago"]
    assert history_args(0) == []      # 0 disables the bound
    assert history_args(-1) == []


def test_churn_respects_the_window(git_project):
    """A commit outside the window must not count toward churn — otherwise
    `torsor coach` gets slower every year and reports files that went quiet
    long ago."""
    import subprocess

    from torsor_helper.coach.hotspots import _churn

    old = git_project / "ancient.py"
    old.write_text("x = 1\n")
    subprocess.run(["git", "-C", str(git_project), "add", "ancient.py"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(git_project), "commit", "-m", "ancient", "--date", "2020-01-01T00:00:00"],
        check=True, capture_output=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "GIT_COMMITTER_DATE": "2020-01-01T00:00:00",
             "GIT_AUTHOR_DATE": "2020-01-01T00:00:00", "HOME": str(git_project)},
    )

    assert "ancient.py" not in _churn(git_project, history_days=30)
    assert "ancient.py" in _churn(git_project, history_days=0)   # unbounded still sees it
