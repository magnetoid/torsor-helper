import os

from torsor_helper.cartographer import iter_files, iter_source_files, scan_repo


def _make_repo(root):
    (root / "pkg").mkdir()
    (root / "pkg" / "dates.py").write_text("def format_date(d):\n    return d\n")
    (root / "app.py").write_text("from pkg.dates import format_date\n\ndef run():\n    return format_date(1)\n")
    (root / ".venv").mkdir()
    (root / ".venv" / "junk.py").write_text("def should_not_appear():\n    pass\n")
    (root / ".torsor").mkdir()
    (root / ".torsor" / "x.py").write_text("def nope():\n    pass\n")


def test_iter_source_files_skips_ignored(tmp_path):
    _make_repo(tmp_path)
    files = [p.relative_to(tmp_path).as_posix() for p in iter_source_files(tmp_path)]
    assert "app.py" in files
    assert "pkg/dates.py" in files
    assert not any(".venv" in f or ".torsor" in f for f in files)


def test_scan_repo_collects_symbols_and_refs(tmp_path):
    _make_repo(tmp_path)
    syms = scan_repo(tmp_path)
    names = {s.name for s in syms}
    assert {"format_date", "run"} <= names
    assert "should_not_appear" not in names
    fmt = next(s for s in syms if s.name == "format_date")
    assert fmt.refs >= 1
    assert fmt.module == "pkg/dates.py"


def test_scan_repo_explicit_paths(tmp_path):
    _make_repo(tmp_path)
    syms = scan_repo(tmp_path, paths=["app.py"])
    assert {s.module for s in syms} == {"app.py"}


def test_scan_handles_utf8_bom(tmp_path):
    (tmp_path / "bom.py").write_text("\ufeffdef f():\n    pass\n", encoding="utf-8")
    syms = scan_repo(tmp_path)
    assert any(s.name == "f" for s in syms)


def test_dotted_python_module_ending_in_a_foreign_suffix_still_resolves(tmp_path):
    # R19 regression: norm_module used to strip ".go" off the dotted import
    # target "pkg.go", so the edge resolved to "pkg" and never matched the
    # symbol's own canonical key "pkg.go".
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "go.py").write_text("def f():\n    return 1\n")
    (tmp_path / "app.py").write_text("from pkg.go import f\n\ndef run():\n    return f()\n")
    syms = scan_repo(tmp_path)
    f = next(s for s in syms if s.name == "f")
    assert f.refs == 1


def test_iter_files_never_descends_into_an_ignored_directory(tmp_path, monkeypatch):
    # R21: pruning must happen during traversal, not after — rglob("*") used to
    # materialize and stat every file under node_modules/.git/.venv first.
    (tmp_path / "node_modules" / "deep").mkdir(parents=True)
    (tmp_path / "node_modules" / "deep" / "x.py").write_text("x = 1\n")
    (tmp_path / "app.py").write_text("y = 1\n")

    real_scandir = os.scandir
    scanned: list[str] = []

    def spy(path="."):
        scanned.append(str(path))
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", spy)
    files = [p.relative_to(tmp_path).as_posix() for p in iter_files(tmp_path)]
    assert files == ["app.py"]
    assert not any("node_modules" in entry for entry in scanned)


def test_iter_files_is_sorted_by_path_across_directory_levels(tmp_path):
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "c.py").write_text("")
    (tmp_path / "a.py").write_text("")
    (tmp_path / "z.py").write_text("")
    assert [p.relative_to(tmp_path).as_posix() for p in iter_files(tmp_path)] == ["a.py", "b/c.py", "z.py"]
