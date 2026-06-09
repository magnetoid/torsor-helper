import subprocess
from datetime import datetime

from torsor_helper import db
from torsor_helper.coach import coupling
from torsor_helper.embeddings import HashingEmbedder
from torsor_helper.indexer import reindex
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 10, 9, 0, 0)


def _coupled_repo(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()

    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    git("init")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "Test")
    git("config", "commit.gpgsign", "false")
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 1\n")
    (tmp_path / "c.py").write_text("z = 1\n")
    git("add", ".")
    git("commit", "-m", "init")
    for i in range(3):  # a.py and b.py always change together
        (tmp_path / "a.py").write_text(f"x = {i}\n")
        (tmp_path / "b.py").write_text(f"y = {i}\n")
        git("add", "a.py", "b.py")
        git("commit", "-m", f"ab {i}")
    (tmp_path / "c.py").write_text("z = 2\n")  # c.py changes alone
    git("add", "c.py")
    git("commit", "-m", "c")
    return store


def test_find_coupling_detects_co_changed_pair(tmp_path):
    _coupled_repo(tmp_path)
    pairs = coupling.find_coupling(tmp_path)
    names = {(a, b) for a, b, _, _ in pairs}
    assert ("a.py", "b.py") in names
    assert not any("c.py" in (a, b) for a, b, _, _ in pairs)  # c.py not strongly coupled


def test_no_coupling_without_git(tmp_project):
    assert coupling.find_coupling(tmp_project) == []


def test_coupling_recs_emitted_when_unlinked(tmp_path):
    store = _coupled_repo(tmp_path)
    conn = db.connect(store.paths.index_db)
    reindex(store, conn, HashingEmbedder(dim=64))
    try:
        recs = coupling.find_coupling_recs(tmp_path, conn)
    finally:
        conn.close()
    assert any(r.kind == "coupling" for r in recs)
    assert any("a.py" in r.source and "b.py" in r.source for r in recs)
