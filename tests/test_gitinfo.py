"""One git wrapper, and it survives paths git has to quote.

Change discovery used to split git's output on whitespace, so a path with a
space became two paths, and git C-quotes non-ASCII names by default, so those
never matched anything. Both are silent: the file is simply never checked.
"""
from __future__ import annotations

import subprocess

import pytest

from torsor_helper import gitinfo


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.t")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "seed.py").write_text("x = 1\n")
    _git(tmp_path, "add", "seed.py")
    _git(tmp_path, "commit", "-m", "seed")
    return tmp_path


def test_head_and_is_repo(repo, tmp_path):
    assert len(gitinfo.head(repo)) == 40
    assert gitinfo.is_repo(repo)
    assert not gitinfo.is_repo(tmp_path.parent / "definitely-not-a-repo")


def test_output_is_empty_on_failure_not_an_exception(tmp_path):
    assert gitinfo.output(tmp_path, "rev-parse", "HEAD") == ""


def test_changed_source_files_sees_edits_and_untracked(repo):
    (repo / "seed.py").write_text("x = 2\n")
    (repo / "new.py").write_text("y = 1\n")
    assert set(gitinfo.changed_source_files(repo)) == {"seed.py", "new.py"}


def test_a_path_with_a_space_stays_one_path(repo):
    (repo / "two words.py").write_text("z = 1\n")
    assert "two words.py" in gitinfo.changed_source_files(repo)


def test_a_non_ascii_path_is_not_c_quoted(repo):
    (repo / "café.py").write_text("z = 1\n")
    changed = gitinfo.changed_source_files(repo)
    assert "café.py" in changed
    assert not any("\\3" in c for c in changed)   # git's octal C-quoting


def test_commit_source_files_reads_one_commit(repo):
    (repo / "later.py").write_text("q = 1\n")
    _git(repo, "add", "later.py")
    _git(repo, "commit", "-m", "later")
    assert gitinfo.commit_source_files(repo) == ["later.py"]


def test_non_source_files_are_filtered_out(repo):
    (repo / "notes.txt").write_text("hello\n")
    (repo / "real.py").write_text("p = 1\n")
    assert gitinfo.changed_source_files(repo) == ["real.py"]
