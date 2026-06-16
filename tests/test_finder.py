import subprocess
from datetime import datetime

from torsor_helper import db, finder
from torsor_helper import operations as ops
from torsor_helper.config import TorsorConfig
from torsor_helper.paths import TorsorPaths
from torsor_helper.store import Store

CLOCK = lambda: datetime(2026, 6, 10, 9, 0, 0)


# ---- fuzzy_score ----

def test_fuzzy_matches_subsequence():
    assert finder.fuzzy_score("carto", "src/torsor_helper/cartographer.py") is not None
    assert finder.fuzzy_score("xyz", "cartographer.py") is None


def test_fuzzy_prefers_basename_match():
    q = "deps"
    direct = finder.fuzzy_score(q, "src/torsor_helper/deps.py")
    nested = finder.fuzzy_score(q, "tests/test_deps.py")
    assert direct is not None and nested is not None
    assert direct > nested  # filename match beats a mid-name match


def test_fuzzy_rewards_contiguous_and_boundary():
    contiguous = finder.fuzzy_score("carto", "cartographer.py")
    scattered = finder.fuzzy_score("carto", "c_a_r_t_o_x.py")
    assert contiguous > scattered


def test_fuzzy_smart_case():
    # lowercase query is case-insensitive; uppercase query is case-sensitive
    assert finder.fuzzy_score("read", "README.md") is not None
    assert finder.fuzzy_score("READ", "readme.md") is None


def test_literal_and_regex_modes():
    assert finder._score("deps", "deps.py", "literal") is not None
    assert finder._score("zzz", "deps.py", "literal") is None
    assert finder._score(r"dep.\.py", "deps.py", "regex") is not None
    assert finder._score("[bad(regex", "deps.py", "regex") is None  # invalid regex → no match


# ---- list_files + find ----

def _git_repo(tmp_path):
    store = Store(TorsorPaths(tmp_path), clock=CLOCK)
    store.scaffold()

    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    git("init")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "Test")
    git("config", "commit.gpgsign", "false")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "dates.py").write_text("def format_date(d):\n    return d\n")
    (tmp_path / "README.md").write_text("# project\n")
    git("add", ".")
    git("commit", "-m", "init")
    return store


def test_list_files_includes_repo_excludes_torsor(tmp_path):
    _git_repo(tmp_path)
    files = finder.list_files(tmp_path)
    assert "pkg/dates.py" in files
    assert "README.md" in files
    assert not any(f.startswith(".torsor") for f in files)


def test_find_returns_files_and_symbols(tmp_path):
    store = _git_repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    res = ops.find_targets(store, TorsorConfig(), "dates")
    assert any(r["type"] == "file" and r["path"] == "pkg/dates.py" for r in res)

    sres = ops.find_targets(store, TorsorConfig(), "format_date")
    assert any(r["type"] == "symbol" and r["name"] == "format_date" for r in sres)


def test_find_files_only_filter(tmp_path):
    store = _git_repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    res = ops.find_targets(store, TorsorConfig(), "format_date", include_symbols=False)
    assert all(r["type"] == "file" for r in res)


def test_find_populates_frecency(tmp_path):
    store = _git_repo(tmp_path)
    ops.map_repo(store, TorsorConfig())
    ops.find_targets(store, TorsorConfig(), "dates")
    conn = db.connect(store.paths.index_db)
    try:
        access = db.path_access_map(conn)
    finally:
        conn.close()
    assert any(p == "pkg/dates.py" and count >= 1 for p, (count, _) in access.items())


def test_path_access_roundtrip_and_schema(tmp_path):
    conn = db.connect(tmp_path / "i.db")
    assert db.SCHEMA_VERSION == 6
    db.bump_path_access(conn, ["a.py", "b.py"])
    db.bump_path_access(conn, ["a.py"])
    access = db.path_access_map(conn)
    assert access["a.py"][0] == 2 and access["b.py"][0] == 1
    assert access["a.py"][1] >= access["b.py"][1]  # a.py seen more recently
